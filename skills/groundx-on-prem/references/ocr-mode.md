# OCR Mode — Tesseract vs Google Cloud Vision

This file documents **the OCR decision a deployer makes once during install** — bundled in-cluster Tesseract vs Google Cloud Vision API — the trust-boundary trade-off, the exact field shape the chart expects (a packaged-file path that renders a Secret, or — on chart 0.2.7 — a pre-created Secret referenced through the top-level `google.existingSecret` value; the packaged path is *not* inline JSON), the egress posture, and the cross-field implications.

For the architectural picture of where OCR sits in the layout pipeline, route to `groundx-architecture/references/layout-ocr.md`. For the discovery-question framing, route to `values-authoring.md` § 3.6.3. For the field-level reference, route to `values-yaml.md` § 5.2.

## 1. The two options

The chart's `groundx.layout.ocr.type` helper defaults to `tesseract` (literal — `dig "type" "tesseract" $in`). Setting `type` to any other value (typically `google`) signals the application to use a different OCR backend.

| Option | `layout.ocr.type` | Where OCR runs | Egress |
| --- | --- | --- | --- |
| **Tesseract (default)** | `tesseract` (or unset) | In-cluster, in the `layout-ocr` pod. No external service call. | None for OCR. |
| **Google Cloud Vision** | `google` | External — Google Cloud Vision API. Page images leave the cluster on every OCR call. | Outbound HTTPS to `vision.googleapis.com`. |

The chart doesn't strictly validate the `type` value (it's a free string passed through to the application's runtime config). `tesseract` and `google` are the values the application is built to handle.

**Migrating from an existing hosted deployment?** These two are the *only* OCR backends the chart supports. A hosted GroundX deployment may run OCR on a backend that has **no chart equivalent** — for example AWS Textract, driven out-of-band by the hosted stack (SNS/Lambda), which the chart cannot reproduce. Migrating onto the chart therefore forces a switch to Tesseract or Google Cloud Vision. Treat that as a functional change, not a lift-and-shift: benchmark OCR output parity on your own document mix before cutover, because OCR-quality differences propagate downstream into layout, chunking, and search results. See `deployment-options.md` § 6 for the broader migration framing.

## 2. Decision matrix

| Dimension | Tesseract | Google Cloud Vision |
| --- | --- | --- |
| **Trust boundary** | Closed — page images stay inside the cluster. **Critical for FedRAMP, regulated verticals, and air-gapped deployments.** | Open — page images leave the cluster on every OCR call. Trust-boundary crossing. See `groundx-architecture/references/identity-and-trust.md` § 6.2. |
| **Cost** | Free (CPU cycles on the layout-ocr pod). | Pay-per-image. Per [GCV pricing](https://cloud.google.com/vision/pricing), typically a fraction of a cent per page. |
| **Quality** | Solid for typed text, English-heavy documents, and standard fonts. Degrades on handwriting, low-resolution scans, and non-Latin scripts. | Higher quality on edge cases — handwriting, mixed scripts, low-resolution scans, photographs of documents. Google's vision models are SOTA-class. |
| **Latency** | In-cluster CPU call, sub-second per page after warm-up. | Network-bound. Adds 100–500 ms per page depending on geography + GCV load. |
| **Air-gap compatibility** | Yes — fully self-contained. | No — outbound internet egress required. |
| **Setup complexity** | None. Default. | Supply a GCP service-account JSON — packaged in the chart (`layout.ocr.credentials`) or, on chart 0.2.7, via a pre-created Secret referenced through the top-level `google.existingSecret` value — set the values fields, configure NetworkPolicy egress. |

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

Four steps. The non-obvious one is step 1. This walks the chart-packaged-file path. To supply the key through a pre-created Secret instead, follow § 7 (`google.existingSecret`): skip step 4.1 **and**, in step 4.2, leave `layout.ocr.credentials` unset and set `google.existingSecret` instead. A non-empty `layout.ocr.credentials` selects the packaged-file path, so leaving it set while step 4.1 is skipped bypasses your Secret and fails the install at the chart's `.Files.Glob` check.

### 4.1 Package the GCP service-account JSON in the chart

The chart consumes the GCV credentials as a **packaged file** — the JSON key is not inline in values.yaml. At template-rendering time, the chart calls `.Files.Glob` against the path you supply, and if the file exists in the chart directory, it materializes a Kubernetes **Secret** named `{layout.serviceName}-ocr-credentials-map` (default `layout-ocr-credentials-map`) carrying the JSON under `stringData.credentials.json`. On chart 0.2.7 the key file can instead be supplied as a pre-created Secret referenced through the top-level `google.existingSecret` value (see § 7); either way the layout-ocr application reads the key file mounted at `/app/credentials.json`.

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
    credentials: files/ocr/credentials.json     # path to the packaged file (step 4.1); OMIT on the pre-created-Secret path
```

For the pre-created-Secret path, omit `credentials` here and set the top-level `google.existingSecret` instead (see § 7). A non-empty `layout.ocr.credentials` selects the packaged-file path, so leaving it set would bypass the pre-created Secret and fail the install when the packaged file is absent.

The chart's helper checks that the file exists at template time and `fail`s the install if it doesn't:

> ```
> {{- if not $matches -}}
>   {{- fail (printf "layout.ocr.credentials file not found at path: %s" $path) -}}
> {{- end -}}
> ```

So a missing or mistyped path is caught at `helm install` / `helm template` time, not at runtime. (A *present, valid* path can still fail to render on chart versions before the Google-OCR render fix, a separate `celery.yaml` whitespace-chomp bug — see `troubleshooting.md` § 1.6.)

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

## 5. How the credential is supplied — packaged file or pre-created Secret

A common reaction: "shouldn't the GCP credentials be a Kubernetes Secret instead of a packaged file?"

They are: the chart renders the packaged file into a Kubernetes Secret (see § 4.1). On chart 0.2.7 the deployer also has the second option directly — hand the chart a reference to a Secret they create and manage, through the top-level `google.existingSecret` value (see § 7), instead of packaging the file. Either way the credential is a JSON key file; the layout-ocr application reads it at `/app/credentials.json` and has no keyless path. The chart-packaged file remains the simplest default because:

1. **OCR credentials are install-time configuration**, not runtime-rotated credentials. The GCP service-account JSON is generated once when the integration is set up; rotation is rare and operator-driven.
2. **The chart's `.Files.Glob` mechanism resolves the packaged file at template-render time**, so a missing packaged file fails the install fast. The `google.existingSecret` path defers that check to pod start, where a missing or wrong Secret surfaces as a mount or startup failure instead.
3. **The Secret stays inside the layout namespace and is never referenced by the `groundx` API pod or the Partner API.** The celery template (`templates/app/celery.yaml`) is what attaches the `credentials-volume` mount, and only celery-rendered pods carry the JSON on disk — the externally-reachable surfaces never receive it. **Note**: the celery template scopes the OCR annotation, the `credentials-volume` mount, and the Secret volume to layout Celery workers only; non-layout celery services — `extract-*`, `workspace-*`, or any custom celery service — receive none of this OCR wiring, whether or not `layout.ocr.credentials` is set. Deployments enabling extract-* or workspace-* celery services concurrently with `layout.ocr.credentials` render and install cleanly, with no unintended reference to a nonexistent extract or workspace OCR credentials resource.

**Compliance implications.** The Secret carrying the service-account JSON — whether the chart renders it from the packaged file or the deployer pre-creates it and references it through `google.existingSecret` — is base64-encoded, not encrypted, at rest in etcd unless the cluster enables encryption at rest (EncryptionConfiguration). For SOC 2 / FedRAMP-stringent deployments:

- Ensure cluster-wide etcd encryption at rest is enabled.
- When using the `google.existingSecret` path, keep the key file out of git — create the Secret directly or through a secret manager rather than packaging the JSON in the chart. Google Cloud Vision OCR has no keyless mode on 0.2.7, so the JSON key file is required either way. See `credentials.md` § 9.

## 6. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `layout.ocr.type: google` | Must also set `layout.ocr.project` (GCP project id) and supply the JSON key file — either `layout.ocr.credentials` (path to a packaged JSON file) or a pre-created Secret via the top-level `google.existingSecret` value. |
| `layout.ocr.credentials: <path>` | The file must exist at `<chart-root>/<path>` at template-render time. The chart's `.Files.Glob` check fails the install otherwise. |
| `layout.ocr.type: google` + air-gapped deployment | **Conflict.** GCV needs outbound internet egress. Use Tesseract for air-gapped. |
| `layout.ocr.type: google` + FedRAMP / HIPAA compliance | **Requires deployer attestation.** GCV is a trust-boundary crossing — update the data-residency posture and confirm BAA / DPA with Google is in place. |
| Switching `type` from `tesseract` to `google` after install | Set `layout.ocr.type: google` + `layout.ocr.project`, then supply the JSON key file one of two ways — ship the packaged file in the chart and set `layout.ocr.credentials`, **or** (chart 0.2.7) reference a pre-created Secret via the top-level `google.existingSecret` value and leave `layout.ocr.credentials` unset — then `helm upgrade --install`. With the packaged file the chart materializes the Secret; with `google.existingSecret` the chart mounts the pre-created Secret. Either way the key is mounted at `/app/credentials.json`, and because the switch adds the OCR volume mount to the pod spec the layout Celery pods restart to pick it up. |
| Switching `type` from `google` to `tesseract` after install | Setting `layout.ocr.type: tesseract` alone does **not** drop a chart-packaged credential: `groundx.layout.hasOCRCredentials` — and the `layout-ocr-credentials-map` Secret gated on it — key only on whether `layout.ocr.credentials` is a non-empty string, never on `type`. So with `layout.ocr.credentials` still set, the Secret stays materialized **and** stays mounted at `/app/credentials.json` (`$mountOCR` stays true via `hasOCR`). To actually remove the Google credential, **also clear `layout.ocr.credentials`** (the packaged-file path). The pre-created-Secret path differs: `sharedGoogle` is type-gated, so for a `google.existingSecret` mount (with `layout.ocr.credentials` unset) setting `type: tesseract` makes `sharedGoogle` go false and that mount drops on its own — the chart never managed that Secret, so leave `google.existingSecret` in place if other Google features use it. Once the mount drops, the layout Celery pods restart to Tesseract-only mode. |

## 7. Supplying the key file via a pre-created Secret (`google.existingSecret`)

On chart 0.2.7, a deployer who manages their own Kubernetes Secrets can skip packaging the JSON file in the chart directory and reference a pre-created Secret instead:

1. Create a Secret in the GroundX namespace (the chart's `namespace` value, default `eyelevel`) holding the GCP service-account JSON under the key `credentials.json` (override the key with `google.secretKey`).
2. Set `layout.ocr.type: google` and `layout.ocr.project`.
3. Set the top-level `google.existingSecret: <secret-name>`.
4. **Leave `layout.ocr.credentials` unset.** With `layout.ocr.type: google`, an empty `layout.ocr.credentials`, and `google.existingSecret` set, the chart mounts the referenced Secret at `/app/credentials.json`.

This is the pre-created-Secret path for operators who do not want the key file in the chart directory.

Google Cloud Vision OCR needs the JSON key file on disk in every case: the layout-ocr application reads it at `/app/credentials.json` and raises at startup if it is absent. There is no keyless (Workload Identity / Application Default Credentials) mode for Google OCR on 0.2.7 — binding a GKE ServiceAccount to a GCP service account does not by itself satisfy the application's key-file requirement. Running OCR without a key file would be an application change, not a values change. `credentials.md` § 9 covers how Workload Identity does replace static credentials for the *cloud* backing services (S3 / RDS / SQS / ElastiCache / OpenSearch).

## 8. What this file does not cover

- **Field-by-field schema for `layout.ocr.*` fields** → `values-yaml.md` § 5.2.
- **Discovery questionnaire that surfaces OCR choice at install time** → `values-authoring.md` § 3.6.3.
- **Architectural picture of OCR in the layout pipeline** → `groundx-architecture/references/layout-ocr.md`.
- **Tesseract vs GCV quality benchmarks** → out of scope; benchmark against the deployer's specific document mix.
- **GCV pricing details** → consult Google Cloud Vision pricing page.
- **NetworkPolicy authoring for egress** → `troubleshooting.md`.
- **Per-pod resource sizing for layout-ocr** → `cluster-requirements.md` § 6 + `node-groups.md`.
