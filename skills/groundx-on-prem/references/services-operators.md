# Services Operators — Strimzi / Percona / MinIO / OpenSearch / NVIDIA

This file documents **the operators (and operator-adjacent Helm releases) that must be installed alongside the GroundX chart when stateful subsystems are deployed in-cluster** — Percona for MySQL, MinIO operator + tenant for object store, OpenSearch's own Helm chart, Strimzi for Kafka, and the NVIDIA GPU Operator for GPU scheduling. The GroundX chart does *not* render these resources itself (with the single exception of `KafkaTopic` CRDs, which Strimzi must already be installed to interpret).

For the *decision* between chart-deploying these subsystems vs routing to existing infrastructure, route to `service-substitution.md`. For chart-side image variant choices (including the canonical Chainguard recipe for each operator), route to `image-variants.md` § 3. For ordering the operator installs vs the GroundX chart install, route to `install-flow.md`. For per-cluster GPU sizing and node-group targets, route to `node-groups.md` and `cluster-requirements.md`.

## 1. The five operators / Helm releases

| Subsystem | Operator / Helm release | What the deployer installs | Values seed file |
| --- | --- | --- | --- |
| **NVIDIA GPU** | NVIDIA GPU Operator (`nvidia/gpu-operator`) | A DaemonSet that provides the `nvidia.com/gpu` resource registration, driver lifecycle, and container runtime configuration. | `src/groundx/values/nvidia/values.yaml` (generic), `values.aks.yaml` (Azure variant) |
| **MySQL** | Percona XtraDB Cluster operator (`percona/pxc-operator`) + Percona XtraDB cluster CR (`percona/pxc-db`) | Two Helm releases: the operator first, then a cluster CR that the operator reconciles into an actual StatefulSet + HAProxy services. | `src/groundx/values/percona/values.operator.yaml`, `values.cluster.yaml` |
| **Object store** | MinIO Operator (`minio-operator/operator`) + MinIO Tenant (`minio-operator/tenant`) | Two Helm releases: the operator, then a tenant CR specifying the actual MinIO cluster shape. | `src/groundx/values/minio/values.operator.yaml`, `values.tenant.yaml` |
| **Search** | OpenSearch's own Helm chart (`opensearch/opensearch`) | Single Helm release. No separate operator. | `src/groundx/values/opensearch/values.yaml` |
| **Stream** | Strimzi Kafka operator (`oci://quay.io/strimzi-helm/strimzi-kafka-operator`) + a `Kafka` cluster CR | Operator via Helm; the cluster CR comes from a separate GroundX-published chart (`groundx/groundx-strimzi-kafka-cluster`). | `src/groundx/values/strimzi/values.yaml` |

Each line is a Helm release the deployer manages **separately from the GroundX chart**. The GroundX chart writes connection strings into `config.yaml` assuming these are deployed in the same namespace with their chart-default service names; if the deployer renames operators/clusters, see § 8.

## 2. NVIDIA GPU Operator

### 2.1 What it provides

The operator registers the `nvidia.com/gpu` extended resource, manages NVIDIA driver installation on each GPU node, and configures the container runtime (containerd / CRI-O) to route GPU-requesting pods correctly. Without it, GroundX's three inference deployments (`layout-inference`, `ranker-inference`, `summary-inference`) schedule on the cluster but fail to acquire GPUs.

### 2.2 Install — generic

```sh
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

helm install nvidia-gpu-operator \
  nvidia/gpu-operator \
  -n nvidia-gpu-operator \
  --create-namespace \
  --atomic \
  -f helm/values/nvidia/values.yaml
```

The chart's seed file (`helm/values/nvidia/values.yaml`, mirrored at `src/groundx/values/nvidia/values.yaml`) is deliberately thin — it only sets `operator.runtimeClass: nvidia`. Real installs typically pin a driver version, set a GPU operator namespace, and configure operator features per the upstream operator docs.

### 2.3 Azure AKS variant — `runtimeClass: nvidia-container-runtime`

On Azure AKS, the GPU operator needs `runtimeClass: nvidia-container-runtime` (different from the generic `nvidia`). The chart ships an AKS-specific seed at `helm/values/nvidia/values.aks.yaml`:

```yaml
operator:
  runtimeClass: nvidia-container-runtime
```

Apply this seed when installing on AKS:

```sh
helm install nvidia-gpu-operator nvidia/gpu-operator \
  -n nvidia-gpu-operator \
  --create-namespace \
  --atomic \
  -f helm/values/nvidia/values.aks.yaml
```

### 2.4 What GroundX assumes after install

- Pods requesting `nvidia.com/gpu` resources schedule on nodes labeled with the `eyelevel-gpu-*` labels (see `node-groups.md`).
- Each GPU node exposes one or more `nvidia.com/gpu` resources to the scheduler.
- The CUDA-based GroundX inference images run successfully on the nodes' driver / runtime combo.

For per-microservice GPU memory minimums and recommended GPU model classes, route to `cluster-requirements.md` § 2.

## 3. Percona XtraDB — MySQL cluster

### 3.1 Two-step install

The Percona pattern requires two Helm releases. The operator must be installed and reconcile its CRDs before the cluster CR is created:

```sh
helm repo add percona https://percona.github.io/percona-helm-charts/
helm repo update

helm install db-operator \
  percona/pxc-operator \
  -n eyelevel \
  -f helm/values/percona/values.operator.yaml

helm install db-cluster \
  percona/pxc-db \
  -n eyelevel \
  -f helm/values/percona/values.cluster.yaml
```

The chart's seed files set:

- **`db-operator`**: `nameOverride: db-operator`, `nodeSelector.node: eyelevel-cpu-only`.
- **`db-cluster`**: `nameOverride: db-cluster`, `haproxy.enabled: true` (size 1), `pxc.size: 1` (single-node MySQL), `pxc.persistence.size: 20Gi`, default secrets passwords (`root`, `xtrabackup`, `monitor`, `clustercheck`, `proxyadmin`, `operator`, `replication` all default to `password`), `nodeSelector.node: eyelevel-cpu-only`. `unsafeFlags.pxcSize: true` and `unsafeFlags.proxySize: true` allow the size: 1 configuration (which the operator would otherwise reject as unsafe).

### 3.2 What the GroundX chart assumes about service names

The GroundX chart's `groundx.db.ro` and `groundx.db.rw` helpers hardcode (when no `db.existing` is set) the addresses:

- `ro_addr` → `{db.serviceName}-cluster-haproxy-replicas.{namespace}.svc.cluster.local`
- `rw_addr` → `{db.serviceName}-cluster-haproxy.{namespace}.svc.cluster.local`

Where `db.serviceName` defaults to `db`. So the Percona cluster release **must** be named such that HAProxy services land at `db-cluster-haproxy[-replicas]` in the same namespace. The seed `nameOverride: db-cluster` plus install `helm install db-cluster ...` achieves this. Renaming either side requires keeping both in sync (see § 8).

### 3.3 Rotating Percona secrets

The seed sets default passwords (`password`) for development. Production installs must override `secrets.passwords.*` and rotate them via:

```sh
helm upgrade db-cluster percona/pxc-db \
  -n eyelevel \
  -f my-production-secrets.yaml
```

The operator handles in-place password rotation across cluster nodes.

## 4. MinIO Operator + Tenant

### 4.1 Two-step install

```sh
helm repo add minio-operator https://operator.min.io/
helm repo update

helm install minio-operator \
  minio-operator/operator \
  -n eyelevel \
  -f helm/values/minio/values.operator.yaml

helm install minio-cluster \
  minio-operator/tenant \
  -n eyelevel \
  -f helm/values/minio/values.tenant.yaml
```

### 4.2 Seed values

- **operator**: `operator.nodeSelector.node: eyelevel-cpu-only`, `operator.replicaCount: 1`.
- **tenant**: `tenant.name: minio-tenant`, `tenant.certificate.requestAutoCert: false` (no auto-TLS), `tenant.configSecret: accessKey: minio, secretKey: minio123` (defaults — rotate for production), `tenant.pools[0].servers: 1, size: 20Gi, volumesPerServer: 1, nodeSelector.node: eyelevel-cpu-only`.

### 4.3 What the GroundX chart assumes

The chart's `groundx.file.serviceName` defaults to `minio`. The chart's `groundx.file.bucketDomain` helper (`_helpers/services/file.tpl:130–131`) constructs the in-cluster host as `{file.serviceName}-tenant-hl.{namespace}.svc.cluster.local` — i.e., `minio-tenant-hl.{namespace}.svc.cluster.local` with defaults. The MinIO operator's tenant convention creates a headless service named `{tenant.name}-hl`, so the seed file's `tenant.name: minio-tenant` aligns with `file.serviceName: minio`. Renaming requires changing both sides to keep `{file.serviceName}-tenant-hl` and `{tenant.name}-hl` matching.

For the chart's bucket naming (`file.bucketName`), the deployer must ensure the bucket exists. MinIO Operator's tenant CR can be configured with a `buckets:` block to pre-create buckets, or the deployer creates them manually after install via `mc mb` against the tenant.

## 5. OpenSearch

### 5.1 Single-step install (no separate operator)

```sh
helm repo add opensearch https://opensearch-project.github.io/helm-charts/
helm repo update

helm install opensearch opensearch/opensearch -n eyelevel -f helm/values/opensearch/values.yaml
```

### 5.2 Seed values

The seed `src/groundx/values/opensearch/values.yaml` sets:

- `clusterName: opensearch-cluster`
- `nodeGroup: master`
- `nodeSelector.node: eyelevel-cpu-only`
- `singleNode: true` (single-node OpenSearch, sufficient for development; production deployments increase replicas)
- `persistence.enabled: true, size: 20Gi, enableInitChown: false`
- `replicas: 1`
- `resources.requests: {cpu: 200m, memory: 512Mi}`
- `majorVersion: 2.16.0`
- Image: `public.ecr.aws/c9r4x6y5/eyelevel/opensearch:latest` (chart-distributed copy)
- `extraEnvs[].OPENSEARCH_INITIAL_ADMIN_PASSWORD: R0otb_*t!kazs` (matches the GroundX chart's `search.privilegedPassword` default)

### 5.3 What the GroundX chart assumes

The chart's `groundx.search.serviceName` defaults to `opensearch`. The OpenSearch service lands at `opensearch-cluster-master.{namespace}.svc.cluster.local:9200` via the chart's standard naming pattern. The GroundX chart authenticates via `search.privilegedUsername` / `search.privilegedPassword` during init and `search.username` / `search.password` at runtime — both must match what's set in the OpenSearch deployment (the seed file aligns them).

## 6. Strimzi Kafka

### 6.1 Two-step install

Strimzi's operator first, then a chart-published `Kafka` cluster CR:

```sh
helm install stream-operator \
  oci://quay.io/strimzi-helm/strimzi-kafka-operator \
  -n eyelevel \
  -f helm/values/strimzi/values.yaml
```

Once the operator is ready (the `Kafka` CRD must be registered):

```sh
helm install groundx-kafka-cluster \
  groundx/groundx-strimzi-kafka-cluster \
  -n eyelevel
```

### 6.2 Seed values

The Strimzi seed (`src/groundx/values/strimzi/values.yaml`) is minimal:

```yaml
nodeSelector:
  node: eyelevel-cpu-only
replicas: 1
```

The `groundx-strimzi-kafka-cluster` chart is a separate GroundX-published Helm release that emits the `Kafka` cluster CR with chart-aligned topic names, ports, and broker counts. Its values surface is independent of the main GroundX chart's `stream.*` block.

### 6.3 What the GroundX chart assumes

The GroundX chart renders `KafkaTopic` CRDs (`templates/services/stream-topics.yaml`) for each of the five pipeline topic-keys in `stream.topics.*` — namely `preProcess`, `process`, `summary`, `update`, `upload` — **only when both** `groundx.stream.create` returns non-`"false"` (i.e., stream is not externalized via `existing.domain` and not disabled via `enabled: false`) **and** the per-topic `type` is `"kafka"` (the default). A topic with `type: sqs` (or any non-kafka value) skips its KafkaTopic CRD. The actual Kubernetes `KafkaTopic` resources rendered carry the per-topic `topic:` value, defaulting to `file-pre-process`, `file-process`, `file-summary`, `file-update`, `file-upload` (verified against `tests/__snapshot__/stream_test.yaml.snap`). The cluster itself — the `Kafka` CR — is rendered by the separate `groundx-strimzi-kafka-cluster` release, not by the GroundX chart.

`groundx.stream.serviceName` defaults to `stream`. The GroundX chart's `groundx.stream.serviceHost` helper (`_helpers/services/stream.tpl:76–80`) routes to `{stream.serviceName}-cluster-kafka-bootstrap.{namespace}.svc.cluster.local` — i.e., `stream-cluster-kafka-bootstrap.{namespace}.svc.cluster.local` with defaults. This follows the Strimzi convention `<kafka-cr-name>-kafka-bootstrap`, so the `groundx-strimzi-kafka-cluster` release must produce a `Kafka` CR named `stream-cluster` (or whatever matches `{stream.serviceName}-cluster`).

## 7. Chainguard variants

For deployers running the GroundX chart with `imageType: chainguard`, the chart ships paired Chainguard seed files under `src/groundx/values/chainguard/` for **four** of the five operators (no OpenSearch Chainguard variant ships in the chart — deployer-supplied overrides are required for OpenSearch on Chainguard):

| Subsystem | Chainguard seed file | What it does |
| --- | --- | --- |
| MinIO operator | `values.minio.operator.yaml` | Pins operator image to `cgr.dev/eyelevel.ai/minio-operator-fips`. References `chainguard-pull-secret`. |
| MinIO tenant | `values.minio.tenant.yaml` | Pins tenant image to `cgr.dev/eyelevel.ai/minio-fips`. References `chainguard-pull-secret`. |
| Strimzi operator | `values.strimzi.operator.yaml` | Pins all Strimzi operator + worker images to `cgr.dev/eyelevel.ai/strimzi-kafka-operator` and `cgr.dev/eyelevel.ai/strimzi-kafka`. References `chainguard-pull-secret`. |
| Strimzi Kafka cluster | `values.strimzi.cluster.yaml` | Sets `node: eyelevel-cpu` and `cluster.version: 4.1.0`. Does **not** reference `chainguard-pull-secret` directly — the cluster CR inherits image-pull configuration from the Strimzi operator. |
| NVIDIA | `values.nvidia.yaml` | Sets `operator.runtimeClass: nvidia-container-runtime`. Does **not** override NVIDIA operator images — those come from the upstream NVIDIA registry. The Chainguard NVIDIA variant overlaps content-wise with the AKS-specific seed. |
| **OpenSearch** | None shipped | Deployers running OpenSearch on Chainguard must supply their own image overrides for the OpenSearch Helm chart. |

Layer the Chainguard seed onto the standard seed for each operator install. For example, MinIO operator with Chainguard:

```sh
helm install minio-operator minio-operator/operator \
  -n eyelevel \
  -f helm/values/minio/values.operator.yaml \
  -f helm/values/chainguard/values.minio.operator.yaml
```

The MinIO and Strimzi operator Chainguard seeds reference `chainguard-pull-secret` for image-pull authentication; the deployer creates this secret in the install namespace before the install (see `image-variants.md` § 6). The Strimzi *cluster* and NVIDIA Chainguard seeds inherit their pull-secret configuration from the corresponding operator's release.

## 8. Renaming releases — propagating service-name overrides

The GroundX chart and each operator-managed Helm release agree on service names. If a deployer renames either side, both must stay in sync:

| If you set... | …in the GroundX chart, the operator release must produce... |
| --- | --- |
| `db.serviceName: my-db` | Percona services at `my-db-cluster-haproxy.{ns}.svc.cluster.local` and `my-db-cluster-haproxy-replicas.{ns}.svc.cluster.local`. Typically: `helm install my-db-cluster percona/pxc-db` with `nameOverride: my-db-cluster`. |
| `file.serviceName: my-minio` | MinIO headless service at `my-minio-tenant-hl.{ns}.svc.cluster.local`. The MinIO operator's tenant CR creates `{tenant.name}-hl`, so set `tenant.name: my-minio-tenant`. |
| `search.serviceName: my-search` | OpenSearch master service at `my-search-cluster-master.{ns}.svc.cluster.local`. The OpenSearch Helm chart creates `{clusterName}-master`, so set `clusterName: my-search-cluster`. |
| `stream.serviceName: my-stream` | Strimzi bootstrap service at `my-stream-cluster-kafka-bootstrap.{ns}.svc.cluster.local`. Strimzi creates `{kafka-cr-name}-kafka-bootstrap`, so the `Kafka` CR must be named `my-stream-cluster` (in the `groundx-strimzi-kafka-cluster` release). |

Mismatch yields "no such host" errors in the GroundX pods' connection logs. Run `helm template` against both releases before install to verify the service names align.

## 9. Operator vs cluster — what depends on what

The Helm install ordering matters:

1. **NVIDIA GPU Operator first** if the deployment uses any GPU (most do). The operator's DaemonSet must register `nvidia.com/gpu` on the nodes before GroundX's inference pods can schedule.
2. **Percona operator + cluster** before the GroundX chart. The chart's pods wait for `db.rw` to be reachable (init containers) and fail to start if the Percona cluster isn't running.
3. **MinIO operator + tenant** before the GroundX chart. Same wait pattern via the pre-process / extract / layout pods, which read from MinIO.
4. **OpenSearch** before the GroundX chart, unless `mode: ingest` is set (which disables search entirely). Search-using deployments wait for the OpenSearch service.
5. **Strimzi operator + Kafka cluster** before the GroundX chart. The GroundX chart renders `KafkaTopic` CRDs that the Strimzi operator must be present to interpret. The Kafka cluster must be running for the pipeline pods to send/receive messages.

The full ordered install workflow (with chart-side knobs and validation checks) lives in `install-flow.md`.

## 10. What this file does not cover

- **The substitution decision (chart-deployed vs cloud-managed vs existing in-cluster)** → `service-substitution.md`.
- **The chart's per-subsystem `existing.*` field surface** → `service-substitution.md` § 4.
- **The chart's per-pod resource and replica defaults** → `node-groups.md`, `cluster-requirements.md`.
- **Helm install command sequencing (install-flow ordering)** → `install-flow.md`.
- **NVIDIA GPU Operator deep-dive (driver versions, MIG, time-slicing, troubleshooting)** → `gpu-operator.md`.
- **TLS-cert provisioning for backing services** → `tls-and-certs.md`.
- **Backup / restore strategy for each backing service** → operator-specific docs upstream; not chart-side.
- **OpenShift-specific operator considerations** → `openshift.md`.
- **Air-gapped operator-image mirroring** → `air-gapped.md`.
