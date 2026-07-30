# Air-Gapped Deployment

This file documents **how to run GroundX in an air-gapped cluster** — clusters that have no outbound internet egress. Covers image mirroring (chart pods, backing services, GPU Operator, busybox), `admin.imageRepository` re-pointing, the engines / OCR / metrics choices that conflict with air-gapped, and the pre-install staging procedure.

For the image-variant story (Chainguard hardened images, busybox), route to `image-variants.md`. For the `admin.imageRepository` field mechanics, route to `license-and-admin.md` § 4. For the OCR-side trust-boundary implications, route to `ocr-mode.md` § 2.

## 1. What "air-gapped" means here

An **air-gapped cluster** is a Kubernetes cluster with no outbound internet egress — pods cannot reach `public.ecr.aws`, `cgr.dev`, `api.openai.com`, `vision.googleapis.com`, etc. All container images, Helm charts, dependencies, and runtime API calls must be served from inside the deployer's network.

Common deployment contexts: government / FedRAMP, defense, regulated finance, on-prem manufacturing, classified research.

The GroundX chart **supports** air-gapped deployment, but the deployer takes on responsibility for: mirroring every image, replacing every external runtime call with an in-cluster equivalent, and confirming the chart's runtime config doesn't accidentally egress.

## 2. The full image set to mirror

Every container image the cluster pulls — whether for the GroundX chart pods, the backing services, the operators, or auxiliary tooling — must be mirrored into a registry the cluster can reach.

| Image source | Default registry | Mirror target |
| --- | --- | --- |
| GroundX chart pods | `public.ecr.aws/c9r4x6y5/eyelevel/*` | Override via `admin.imageRepository: my-mirror.internal/c9r4x6y5` |
| Chainguard variants (if `imageType: chainguard`) | `cgr.dev/eyelevel.ai/*` | Override per-pod `image:` to `my-mirror.internal/eyelevel.ai/*` |
| Busybox helper | `public.ecr.aws/c9r4x6y5/eyelevel/busybox:1.0.0` or `cgr.dev/eyelevel.ai/busybox-fips:latest` | `busybox.image: my-mirror.internal/...` |
| NVIDIA GPU Operator | `nvcr.io/nvidia/*`, `nvcr.io/nvidia/cloud-native/*` | Mirror all NVIDIA images; pin operator install via offline values |
| Percona PXC operator + cluster | `percona/*` (Docker Hub) | Mirror via Percona's air-gapped install procedure |
| MinIO operator + tenant | `minio/operator`, `minio/tenant`, `quay.io/minio/*` | Mirror; reference local image in tenant.image |
| Strimzi Kafka operator | `quay.io/strimzi/*` | Mirror; use offline values for the operator and cluster Helm releases |
| OpenSearch | `opensearchproject/opensearch`, `opensearchproject/opensearch-dashboards` | Mirror |
| Redis | `redis:*` from Docker Hub (in-cluster cache mode) | Mirror |

Common mirror choices: AWS ECR (within the deployer's account, when AWS is the host), Harbor on-prem, Nexus Repository, Artifactory, or a tarball-driven `docker save` / `crictl pull` workflow on each node.

## 3. Re-pointing the chart-wide image prefix

The chart's per-pod image helpers build paths as `{admin.imageRepository}/eyelevel/<service>:<tag>` (default prefix `public.ecr.aws/c9r4x6y5` when admin.imageRepository is unset). Re-point all chart pod images at once via:

```yaml
admin:
  imageRepository: my-mirror.internal/c9r4x6y5
```

This affects every pod that uses the chart's *fallback* image path. Per-pod overrides via `<pod>.image: <full-path>` still take precedence, so for hybrid scenarios (some pods from the mirror prefix, others as explicit overrides) override the specific cases.

See `license-and-admin.md` § 4 for the `admin.imageRepository` mechanics and `image-variants.md` § 5 for the air-gapped Chainguard combination.

## 4. Per-pod image overrides — when the prefix isn't enough

For pods where the image tag in your mirror differs from the chart's default tag, override the full image path:

```yaml
layout:
  ocr:
    image: my-mirror.internal/c9r4x6y5/eyelevel/layout-process:v2.4.1-private
```

This bypasses the chart's `coalesce` over the fallback. Pod-level `image:` is always literal.

## 5. Image-pull credentials

The mirror typically requires authentication. Create a Kubernetes secret in the install namespace:

```sh
kubectl -n eyelevel create secret docker-registry mirror-pull-secret \
  --docker-server=my-mirror.internal \
  --docker-username=<user> \
  --docker-password=<pass>
```

Reference it in `cluster.imagePullSecrets`:

```yaml
cluster:
  imagePullSecrets:
    - mirror-pull-secret
```

For multiple secrets (e.g., one for the chart-image mirror and another for the Chainguard-image mirror), the list takes both names. See `credentials.md` § 5.

## 6. Engine choices that conflict with air-gapped

Air-gapped deployments force chart-side choices to avoid external egress:

| Default behaviour | Conflict with air-gapped | Required override |
| --- | --- | --- |
| Summary inference via external LLM (`summary.existing.url: https://api.openai.com/v1`) | OpenAI / Azure / Bedrock unreachable | Use self-hosted summary inference: omit `summary.existing.*`, enable `summary.api.enabled: true` + `summary.inference.enabled: true`. See `engines.md`. |
| Layout OCR via Google Cloud Vision (`layout.ocr.type: google`) | `vision.googleapis.com` unreachable | Use Tesseract: `layout.ocr.type: tesseract` (default). See `ocr-mode.md` § 2. |
| Cloud-managed backing services (RDS, MSK, ElastiCache, S3, OpenSearch Service) | All unreachable | Run all backing services in-cluster via operators (Mode 2). See `service-substitution.md` § 5. |
| ServiceMonitor scraping external Prometheus | Out-of-cluster Prometheus unreachable | Run Prometheus in-cluster (`kube-prometheus-stack` per `monitoring.md`). |

**The air-gapped reference deployment is fully self-contained:** chart-deploys all backing services via in-cluster operators, uses self-hosted summary inference (Gemma 3 on a GPU), uses Tesseract OCR, and runs Prometheus / Grafana inside the same cluster.

## 7. Helm chart distribution

The chart itself must be available offline. Two patterns:

### 7.1 Tarball

```sh
# On a network-connected machine
helm package src/groundx -d /tmp
# /tmp/groundx-X.Y.Z.tgz

# Transfer the tarball into the air-gapped environment, then:
helm install groundx /path/to/groundx-X.Y.Z.tgz -n eyelevel -f my-values.yaml
```

### 7.2 Internal Helm repository

Mirror the chart into a Harbor / Artifactory / ChartMuseum instance inside the air-gapped network. Then `helm repo add` points at the internal repo.

## 8. Pre-install staging procedure

Before `helm install` in an air-gapped cluster:

1. **Inventory every image the chart's vanilla install pulls.** Run `helm template -f my-values.yaml ./src/groundx | grep 'image:' | sort -u`. Save the list.
2. **Add the backing-service operator images** (Percona, MinIO, Strimzi, OpenSearch — each operator's chart has its own image list).
3. **Add NVIDIA GPU Operator images** (operator itself + driver + device plugin + DCGM exporter, when applicable).
4. **Add the busybox helper image**.
5. **Mirror every image to your internal registry.** Verify with `crictl pull` or `docker pull` against the mirror from a node.
6. **Set `admin.imageRepository`, `cluster.imagePullSecrets`, and per-pod overrides** to reference the mirror.
7. **Disable external engines** (summary external, Google Cloud Vision OCR).
8. **Run `helm template -f my-values.yaml ./src/groundx`** locally and grep for any remaining external references (`grep -E 'cgr.dev|public.ecr|nvcr.io|googleapis|amazonaws|openai'`). Any hits are leaks to be patched.
9. **Install.** `helm install groundx /path/to/chart.tgz -n eyelevel -f my-values.yaml`.

## 9. Runtime egress verification

After install, verify no pod can reach the public internet:

```sh
# Exec into a chart pod and try to reach an external host
kubectl -n eyelevel exec groundx-xxx -- wget --timeout=5 https://example.com

# Expected: connection timeout / DNS failure
```

If a connection succeeds, the cluster has unintended egress. Common culprits: NodePort or LoadBalancer services with default-allow egress, init-container `wait-for-callback` patterns pointing at external hosts, runtime config that references external endpoints.

NetworkPolicy is the right tool to *enforce* the air gap at the K8s layer:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-egress-to-internet
  namespace: eyelevel
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: eyelevel
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      # No external CIDRs — all egress restricted to in-cluster namespaces
```

## 10. Updates and patches

Air-gapped clusters can't pull updates automatically. The update procedure:

1. **On a network-connected machine**, pull the new chart version and new images.
2. **Test against a representative network-connected environment** (staging mirror), verify behaviour.
3. **Mirror new images into the air-gapped registry**.
4. **Transfer new chart tarball into the air-gapped environment**.
5. **`helm upgrade`** with the new chart + new image references.

See `upgrades.md` for the general upgrade flow; air-gapped just adds the mirror-and-transfer step at the front.

## 11. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| Air-gapped cluster | All operator releases (Percona, MinIO, Strimzi, OpenSearch, NVIDIA GPU Operator, Prometheus) must also be air-gapped — each operator's images mirrored, charts mirrored. |
| `summary.existing.url: https://api.openai.com/v1` in an air-gapped cluster | Pod can't reach the URL; summary calls fail. Use self-hosted summary inference. |
| `layout.ocr.type: google` in an air-gapped cluster | Pod can't reach `vision.googleapis.com`; OCR calls fail. Use Tesseract (the chart default). |
| `admin.imageRepository` unset in an air-gapped cluster | All chart pods try to pull from `public.ecr.aws/c9r4x6y5` — fail. Must override. |
| `cluster.imagePullSecrets` empty in an air-gapped cluster | If the mirror requires auth, all pulls fail. Provision the secret and reference it. |
| Updates / patches | Each upgrade requires the mirror-and-transfer cycle (§ 10). Budget operational time accordingly. |

## 12. What this file does not cover

- **The `admin.imageRepository` field mechanics** → `license-and-admin.md` § 4.
- **Chainguard image-variant choices** → `image-variants.md`.
- **Per-pod image override pattern** → `image-variants.md` § 4.
- **OCR engine choice** → `ocr-mode.md` § 2.
- **External LLM engine choice** → `engines.md`.
- **Backing-service substitution decisions** → `service-substitution.md`.
- **Network-policy authoring beyond the deny-egress sketch** → upstream Kubernetes NetworkPolicy docs.
- **Specific registry mirror tools** (Harbor, Nexus, Artifactory, ECR) → vendor docs.
- **Vulnerability scanning of mirrored images** → out of chart scope; deployer's compliance toolchain.
