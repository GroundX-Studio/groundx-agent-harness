# OCR Mode — Tesseract vs Google Cloud Vision

This file documents **the OCR decision a deployer makes once during install** — bundled in-cluster Tesseract vs Google Cloud Vision API — the trust-boundary trade-off, the exact field shape the chart expects (a packaged-file path, *not* inline JSON or a Secret), the egress posture, and the cross-field implications.

For the architectural picture of where OCR sits in the layout pipeline, route to `groundx-architecture/references/layout-ocr.md`. For the discovery-question framing, route to `values-authoring.md` § 3.6.3. For the field-level reference, route to `values-yaml.md` § 5.2.

## 1. The two options

The chart's `groundx.layout.ocr.type` helper defaults to `tesseract` (literal — `dig "type" "tesseract" $in`). Setting `type` to any other value (typically `google`) signals the application to use a different OCR backend.

| Option | `layout.ocr.type` | Where OCR runs | Egress |
| --- | --- | --- | --- |
| **Tesseract (default)** | `tesseract` (or unset) | In-cluster, in the `layout-ocr` pod. No external service call. | None for OCR. |
| **Google Cloud Vision** | `google` | External — Google Cloud Vision API. Page images leave the cluster on every OCR call. | Outbound HTTPS to `vision.googleapis.com`. |

The chart doesn't strictly validate the `type` value (it's a free string passed through to the application's runtime config). `tesseract` and `google` are the values the application is built to handle.

## 2. Decision matrix

| Dimension | Tesseract | Google Cloud Vision |
| --- | --- | --- |
| **Trust boundary** | Closed — page images stay inside the cluster. **Critical for FedRAMP, regulated verticals, and air-gapped deployments.** | Open — page images leave the cluster on every OCR call. Trust-boundary crossing. See `groundx-architecture/references/identity-and-trust.md` § 6.2. |
| **Cost** | Free (CPU cycles on the layout-ocr pod). | Pay-per-image. Per [GCV pricing](https://cloud.google.com/vision/pricing), typically a fraction of a cent per page. |
| **Quality** | Solid for typed text, English-heavy documents, and standard fonts. Degrades on handwriting, low-resolution scans, and non-Latin scripts. | Higher quality on edge cases — handwriting, mixed scripts, low-resolution scans, photographs of documents. Google's vision models are SOTA-class. |
| **Latency** | In-cluster CPU call, sub-second per page after warm-up. | Network-bound. Adds 100–500 ms per page depending on geography + GCV load. |
| **Air-gap compatibility** | Yes — fully self-contained. | No — outbound internet egress required. |
| **Setup complexity** | None. Default. | Package a GCP service-account JSON in the chart, set 3 values fields, configure NetworkPolicy egress. |

**Two general patterns:**

1. **Regulated / air-gapped / cost-sensitive → Tesseract.** Default and stays cheap.
2. **Non-regulated + document-quality matters → Google Cloud Vision.** Worth it for handwriting / mixed-script / low-quality-scan-heavy corpora.

## 3. Tesseract — default setup

No values.yaml changes needed. The default chart deploys layout-ocr with Tesseract built in.

```yaml
# (no layout.ocr block needed for Tesseract — it's the default)
```

Optionally tune Tesseract sizing per `values-yaml.md` § 5.2:

```yaml
layout:
  ocr:
    replicas:
      desired: 2
    workers: 2
    threads: 2
    resources:
      requests:
        cpu: 1
        memory: 1Gi
```

## 4. Google Cloud Vision — full setup

Four steps. The non-obvious one is step 1.

### 4.1 Package the GCP service-account JSON in the chart

The chart consumes the GCV credentials as a **packaged file**, not inline JSON or a Kubernetes Secret. At template-rendering time, the chart calls `.Files.Glob` against the path you supply, and if the file exists in the chart directory, it materializes a `ConfigMap` named `{layout.serviceName}-ocr-credentials-map` (default `layout-ocr-credentials-map`) carrying the JSON as `credentials.json`.

Place the GCP service-account JSON at a path inside the chart, e.g.:

```sh
cp /path/to/gcp-service-account.json src/groundx/files/ocr/credentials.json
```

The path is relative to the chart root. Conventional choice: `files/ocr/credentials.json`.

### 4.2 Set the three values.yaml fields

```yaml
layout:
  ocr:
    type: google                                # default is "tesseract"; set to "google" for GCV
    project: <gcp-project-id>                    # GCP project for the service account
    credentials: files/ocr/credentials.json     # path to the packaged file (step 4.1)
```

The chart's helper checks that the file exists at template time and `fail`s the install if it doesn't:

> ```
> {{- if not $matches -}}
>   {{- fail (printf "layout.ocr.credentials file not found at path: %s" $path) -}}
> {{- end -}}
> ```

So a missing or mistyped path is caught at `helm install` / `helm template` time, not at runtime.

### 4.3 Allow egress to vision.googleapis.com

The `layout-ocr` pod makes outbound HTTPS calls to Google Cloud Vision. NetworkPolicy must allow egress:

- Destination: `vision.googleapis.com` (port 443).
- Source: pods labeled with the chart's default `app: "layout-ocr"` label (the chart uses the legacy `app` label scheme rather than `app.kubernetes.io/component`; see `templates/_helpers/elements/labels.tpl`).

For air-gapped clusters, GCV is not viable — there's no path from inside the cluster to Google's APIs. Use Tesseract.

### 4.4 Audit the trust-boundary crossing

Document each OCR call now sends a page image to a third party. Update:

- The deployment's data-residency posture (see `groundx-architecture/references/data-residency.md`).
- The compliance attestation if the deployment is under FedRAMP / HIPAA / SOC 2 review — GCV likely requires a BAA or DPA.
- The egress audit log if the cluster has one.

## 5. The credential is a packaged file, not a Secret — why?

A common reaction: "shouldn't the GCP credentials be a Kubernetes Secret instead of a packaged file?"

The chart treats them as a packaged file because:

1. **OCR credentials are install-time configuration**, not runtime-rotated credentials. The GCP service-account JSON is generated once when the integration is set up; rotation is rare and operator-driven.
2. **The chart's `.Files.Glob` mechanism requires the file at template-render time.** Deferring it to a runtime-mounted Secret would mean the chart can't fail-fast on a missing file.
3. **The ConfigMap stays inside the layout namespace and is never referenced by the `groundx` API pod or the Partner API.** The celery template (`templates/app/celery.yaml`) is what attaches the `credentials-volume` mount, and only celery-rendered pods carry the JSON on disk — the externally-reachable surfaces never receive it. **Note**: the celery template's volume reference is keyed on the per-iteration `service` field, so when `$hasOCR = "true"` the mount is added to every celery-rendered Deployment (layout-*, extract-*, workspace-*); only the `layout-*` services have a matching ConfigMap materialized (named `{layout.serviceName}-ocr-credentials-map`). In typical GCV-enabled deployments only the layout-* celery services are scheduled, and the reference resolves cleanly. Deployments enabling extract-* or workspace-* celery services concurrently with `layout.ocr.credentials` should verify resolution in `helm template` output first.

**Compliance implications.** A ConfigMap carrying a service-account JSON is, in Kubernetes terms, not encrypted at rest in etcd by default (unlike a Secret with EncryptionConfiguration). For SOC 2 / FedRAMP-stringent deployments:

- Ensure cluster-wide etcd encryption at rest is enabled.
- Or override the chart's ConfigMap-based pattern by patching the chart locally to use a Secret reference, then mounting that Secret into the layout-ocr celery pod.
- Or use Google Cloud Workload Identity Federation on GKE — the pod's ServiceAccount is bound to a GCP service account, and no JSON file is needed at all. See `credentials.md` § 9.

## 6. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `layout.ocr.type: google` | Must also set `layout.ocr.project` (GCP project id) and `layout.ocr.credentials` (path to packaged JSON file). |
| `layout.ocr.credentials: <path>` | The file must exist at `<chart-root>/<path>` at template-render time. The chart's `.Files.Glob` check fails the install otherwise. |
| `layout.ocr.type: google` + air-gapped deployment | **Conflict.** GCV needs outbound internet egress. Use Tesseract for air-gapped. |
| `layout.ocr.type: google` + FedRAMP / HIPAA compliance | **Requires deployer attestation.** GCV is a trust-boundary crossing — update the data-residency posture and confirm BAA / DPA with Google is in place. |
| Switching `type` from `tesseract` to `google` after install | Update values.yaml + ship the packaged JSON file in the chart + `helm upgrade --install`. ConfigMap is created automatically. Celery pods restart to pick up the new mount (annotation hash on the ConfigMap forces a rollout). |
| Switching `type` from `google` to `tesseract` after install | Set `layout.ocr.type: tesseract` and remove `credentials`/`project`. ConfigMap is no longer materialized (chart's `groundx.layout.hasOCRCredentials` returns false). Celery pods restart to Tesseract-only mode. |

## 7. Workload Identity (GKE) — the IRSA-equivalent for OCR

When the cluster runs on GKE with Workload Identity Federation, the deployer can skip the packaged-JSON-file pattern entirely:

1. Annotate the chart's `serviceAccount.name` (or per-microservice `layout.ocr.serviceAccount.name`) with `iam.gke.io/gcp-service-account=<sa>@<project>.iam.gserviceaccount.com`.
2. Grant that GCP service account permission to call the Cloud Vision API (the exact IAM role depends on the project's setup — typically a Cloud Vision–scoped role; consult Google's Cloud Vision IAM docs for the current canonical role name).
3. Set `layout.ocr.type: google` and `layout.ocr.project`.
4. **Leave `layout.ocr.credentials` unset.** The application uses Application Default Credentials (ADC) and the bound GCP identity authenticates the call without a JSON file.

This is the cleanest production pattern on GKE. See `credentials.md` § 9 for the broader workload-identity story.

On AWS EKS and Azure AKS, workload-identity-to-GCP federation is also possible but requires more setup (Workload Identity Federation cross-cloud). The packaged-JSON-file pattern is the simpler default off GKE.

## 8. What this file does not cover

- **Field-by-field schema for `layout.ocr.*` fields** → `values-yaml.md` § 5.2.
- **Discovery questionnaire that surfaces OCR choice at install time** → `values-authoring.md` § 3.6.3.
- **Architectural picture of OCR in the layout pipeline** → `groundx-architecture/references/layout-ocr.md`.
- **Tesseract vs GCV quality benchmarks** → out of scope; benchmark against the deployer's specific document mix.
- **GCV pricing details** → consult Google Cloud Vision pricing page.
- **NetworkPolicy authoring for egress** → `troubleshooting.md` (planned) when it ships.
- **Per-pod resource sizing for layout-ocr** → `cluster-requirements.md` § 6 + `node-groups.md`.
