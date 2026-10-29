# Services Operators — Strimzi / Percona / MinIO AIStor / OpenSearch / NVIDIA

This file documents **the operators (and operator-adjacent Helm releases) that must be installed alongside the GroundX chart when stateful subsystems are deployed in-cluster** — Percona for MySQL, the MinIO AIStor operator and object store for the object store, OpenSearch's own Helm chart, Strimzi for Kafka, and the NVIDIA GPU Operator for GPU scheduling. The GroundX chart does *not* render these resources itself (with the single exception of `KafkaTopic` CRDs, which Strimzi must already be installed to interpret).

For the *decision* between chart-deploying these subsystems vs routing to existing infrastructure, route to `service-substitution.md`. For chart-side image variant choices (including the canonical Chainguard recipe for each operator), route to `image-variants.md` § 3. For ordering the operator installs vs the GroundX chart install, route to `install-flow.md`. For per-cluster GPU sizing and node-group targets, route to `node-groups.md` and `cluster-requirements.md`.

## 1. The five operators / Helm releases

| Subsystem | Operator / Helm release | What the deployer installs | Values seed file |
| --- | --- | --- | --- |
| **NVIDIA GPU** | NVIDIA GPU Operator (`nvidia/gpu-operator`) | A DaemonSet that provides the `nvidia.com/gpu` resource registration, driver lifecycle, and container runtime configuration. | `src/groundx/values/nvidia/values.yaml` (generic), `values.aks.yaml` (Azure variant) |
| **MySQL** | Percona XtraDB Cluster operator (`percona/pxc-operator`) + Percona XtraDB cluster CR (`percona/pxc-db`) | Two Helm releases: the operator first, then a cluster CR that the operator reconciles into an actual StatefulSet + HAProxy services. | `src/groundx/values/percona/values.operator.yaml`, `values.cluster.yaml` |
| **Object store** | MinIO AIStor operator (`minio/aistor-operator`) + AIStor object store (`minio/aistor-objectstore`) | Two Helm releases: the operator in namespace `aistor`, which needs the customer's AIStor license in Secret `minio-license`, then the object store named `minio-tenant`. | `src/groundx/values/aistor/values.operator.yaml`, `values.objectstore.yaml` |
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

**Mode 2 constraint:** if the GroundX chart deploys against this operator (chart-deployed dedicated Percona), the chart's `db.privilegedUsername` / `db.privilegedPassword` must equal the root username/password this release seeds — see § 3.1's seed list above — these are dev-only seed defaults; override both sides for production — see `values-authoring.md` section 3.5.2's `db.privilegedUsername`/`db.privilegedPassword` constraint.

## 4. MinIO AIStor

GroundX stores files in one S3-compatible bucket (`file.bucketName`, default `eyelevel`). The on-prem guide installs MinIO AIStor, MinIO's maintained product, under the customer's own AIStor license. Community MinIO, which earlier versions of the guide installed, is archived; § 4.4 covers existing community MinIO installs. For S4, a license-free alternative, or for an existing S3-compatible store or AWS S3, see `service-substitution.md` § 4.3.

### 4.1 Install

If you'd like to install MinIO AIStor to your cluster, you need an AIStor license. GroundX does not ship one. The AIStor Free license covers a single server and allows commercial use but not redistribution; a store with more than one server needs a paid license ([AIStor Free agreement](https://www.min.io/legal/aistor-free-agreement), read 2026-10-13).

These steps install the AIStor operator in namespace `aistor` and an object store named `minio-tenant` in `eyelevel`. With that name and TLS off, the store serves the hosts GroundX uses by default (`minio` and `minio-tenant-hl`), so GroundX needs no `file` settings other than the store's credentials. The chart versions are pinned to the ones GroundX tested (`aistor-operator` 6.0.0 and `aistor-objectstore` 1.1.0); the AIStor repository published newer charts on 2026-10-14.

Add the AIStor repository, store your license as Secret `minio-license` (key `minio.license`) in the operator's namespace, and install the operator:

```bash
helm repo add minio https://helm.min.io/
helm repo update

kubectl create namespace aistor
kubectl -n aistor create secret generic minio-license \
  --from-file=minio.license=<path-to-your-license-file>

helm install aistor-operator \
  minio/aistor-operator \
  --version 6.0.0 \
  -n aistor \
  -f helm/values/aistor/values.operator.yaml
```

The operator values run the operators on the `eyelevel-cpu-only` nodes and turn off the operator's cluster-wide pod webhook and its automatic certificate approval; installs and upgrades worked without them in GroundX's tests.

Choose the object store's root credentials and put them in Secret `minio-tenant-env-configuration`. The object store values read the credentials from this Secret, which keeps them out of the Helm release; the chart also refuses to create the Secret itself with the well-known pair `minio`/`minio123`.

```text
cat > config.env <<'EOF'
export MINIO_ROOT_USER=<access-key>
export MINIO_ROOT_PASSWORD=<secret-key>
EOF
kubectl -n eyelevel create secret generic minio-tenant-env-configuration \
  --from-file=config.env
rm config.env
```

Set GroundX's `file.username` and `file.password` to the same two values. Then install the object store:

```bash
helm install minio-tenant \
  minio/aistor-objectstore \
  --version 1.1.0 \
  -n eyelevel \
  -f helm/values/aistor/values.objectstore.yaml
```

Confirm that the store started with the license in place:

```bash
kubectl -n eyelevel get objectstore minio-tenant
```

The install is complete when `STATE` reads `Initialized` and `HEALTH` reads `green`. Without the `minio-license` Secret, the operator does not create the object store: no store pods or services appear, the state reports that Secret `minio-license` was not found, and GroundX keeps waiting for storage. Creating the Secret in `aistor` is enough; in GroundX's tests the store started about a minute later without a reinstall.

### 4.2 What the AIStor values set

`helm/values/aistor/values.operator.yaml` (mirrored at `src/groundx/values/aistor/values.operator.yaml`):

- `global.operator.nodeSelector.node: eyelevel-cpu-only`
- `global.operator.optOutAutomaticCertificates: true` — turns off the operator's automatic certificate approval.
- `operators.object-store.webhook.enabled: false` — turns off the operator's cluster-wide pod webhook.

`helm/values/aistor/values.objectstore.yaml` (mirrored at `src/groundx/values/aistor/values.objectstore.yaml`):

- `secrets.name: minio-tenant-env-configuration` with `secrets.existingSecret: true` — the root credentials come from the Secret created in § 4.1, not from the values file.
- `objectStore.name: minio-tenant`
- `objectStore.pools[0]`: name `pool-0`, `servers: 1`, `volumesPerServer: 1`, `size: 20Gi`, `nodeSelector.node: eyelevel-cpu-only`, requests `cpu: 100m` and `memory: 256Mi`.
- `objectStore.certificates.disableAutoCert: true` (TLS off).

The values ship no credentials. The deployer chooses the object store's root credentials and stores them in Secret `minio-tenant-env-configuration`; the AIStor chart refuses to create that Secret itself with the pair `minio`/`minio123`. One server is what the AIStor Free license covers; a store with more than one server needs a paid license.

**Mode 2 constraint:** if the GroundX chart deploys against this object store (chart-deployed MinIO AIStor), the chart's `file.username` / `file.password` must equal the root credentials in Secret `minio-tenant-env-configuration` — see `values-authoring.md` section 3.5.1's `file.username`/`file.password` constraint.

### 4.3 What the GroundX chart assumes

The chart's `groundx.file.serviceName` defaults to `minio`, and without `file.existing` the storage type is `minio`. The chart derives two in-cluster hosts from it. `groundx.file.serviceDependency` (`_helpers/services/file.tpl:131–146`) builds `{file.serviceName}-tenant-hl.{namespace}.svc.cluster.local`, i.e. `minio-tenant-hl.{namespace}.svc.cluster.local` with defaults; the app pods' startup wait (`until nc -z …`) and the celery services' default file domain use it. `groundx.file.bucketDomain` (`file.tpl:30–37`) resolves to `groundx.file.serviceHost` (`file.tpl:24–28`): the plain `file.serviceName` host in the release namespace, i.e. `minio.{namespace}.svc.cluster.local` with defaults, which the chart writes into the rendered config as the bucket URL. The AIStor object store named `minio-tenant` with TLS off serves both hosts, so GroundX needs no `file` settings other than the store's credentials. The on-prem README installs the store only under that name and gives no steps for another name (§ 8).

With `fileAccess.enabled` false (the chart default), GroundX's file, X-Ray, and page-image links are unsigned and rely on a public-read policy on the bucket (`file.bucketName`, default `eyelevel`). GroundX sets that policy only on a bucket it creates itself. If the bucket already exists in the AIStor store, because it was copied from another store or an operator created it, apply the anonymous `s3:GetObject` policy from step 3 of the on-prem S4 migration guide ([Migrating from MinIO or AIStor](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/s4.md#migrating-from-minio-or-aistor)). That command targets S4: use the AIStor store's own URL, the root credentials from Secret `minio-tenant-env-configuration`, and the store's region in place of the S4 URL, keys, and region. The policy lets anyone who can reach the store read every object in the bucket, not only those links. With `fileAccess.enabled` true, GroundX does not set this policy and the bucket must stay private: do not apply it, and remove any anonymous grant, because GroundX serves files through the file-access gateway instead (`file-access.md`). On S4 0.3.2, `DeleteBucketPolicy` reports success but keeps the policy ([rh-aiservices-bu/s4#34](https://github.com/rh-aiservices-bu/s4/issues/34)): replace the policy instead, with one that grants `s3:GetObject` only to the S4 service user (`arn:aws:iam:::user/s4admin`), then confirm that an anonymous GET of an object in the bucket is refused.

### 4.4 Existing community MinIO installs

Earlier versions of the on-prem guide installed community MinIO as operator release `minio-operator` and tenant release `minio-cluster` in namespace `eyelevel`. The on-prem [MinIO migration guide](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md) holds the three runbooks for such an install; this skill links them and does not copy their commands. On these three paths the GroundX `file` settings stay as they are, and the storage type stays `minio`. Moving the store's files to S4 instead, a license-free option for small installs, changes the storage type to `s4` (`service-substitution.md` § 4.3.1).

- **Upgrade in place to AIStor** — [Upgrading an Existing MinIO Install to AIStor](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md#upgrading-an-existing-minio-install-to-aistor). The store keeps its name, hosts, and credentials on the same disk. MinIO states that the upgrade is permanent and cannot be reversed, so the runbook's first step snapshots the tenant's disk. That step first stops uploads and waits until no documents are still processing, because processing keeps writing files to the store and anything written after the snapshot is not in it; uploads stay stopped until the runbook's step 8. GroundX has not tested this wait. The upgrade needs Helm 3.17 or later, above the Helm 3.8 floor the rest of this skill assumes, and an AIStor license; a tenant with more than one server needs a paid license. The snapshot step needs a CSI snapshot controller and a `VolumeSnapshotClass` for the storage driver, and GroundX's bundled EKS Terraform installs neither; without CSI snapshot support, snapshot the disk with the provider's tools instead. Before the community tenant is uninstalled, the runbook checks with `helm template` that the AIStor chart accepts the edited values file, so a values error stops the upgrade before storage goes down. On EKS, MinIO's migration tool runs in a container that cannot use the `aws eks get-token` login, so the runbook has the operator replace that login in the step 4 kubeconfig with a short-lived token (valid 15 minutes) and set a new token in the same file before step 9; step 9 uninstalls the community operator only if `protect-crds` succeeds.
- **Restore community MinIO from that snapshot** — [Restoring Community MinIO from the Pre-Upgrade Snapshot](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md#restoring-community-minio-from-the-pre-upgrade-snapshot). Objects written after the snapshot are lost, including everything written while the store ran on AIStor. GroundX's database and search index are not restored, so documents ingested after the snapshot stay listed in GroundX without their files, X-Ray and page images, and must be re-ingested; this follows from where GroundX keeps its data and was not tested. The runbook first confirms that the `VolumeSnapshot` reports `readyToUse` and stops otherwise, because a later step deletes the AIStor-era volume claim; a disk snapshotted with the provider's own tools is restored with the provider's own restore steps instead. Before storage goes down, the runbook stops uploads and waits until no documents are still processing; uploads resume at its step 7. GroundX has not tested this wait. The server image the runbook offers for a customer without their own copy, `ghcr.io/coollabsio/minio@sha256:69b55a1c1c5dc285ce04db96689f5b2102317fc77a50680a1874ca6efd1c87f9`, is a build of community MinIO `RELEASE.2025-10-15T17-29-55Z` published by coollabsio on GHCR, not by MinIO. It is newer than the default server image of tenant chart 7.1.1, and GroundX's tests did not restore a tenant that had run a different server release onto it.
- **Stay on community MinIO** — [Staying on Community MinIO](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md#staying-on-community-minio). The store receives no fixes: MinIO archived the community server and operator repositories. As of 2026-10-14 the default server image of tenant chart 7.1.1 no longer downloads anonymously, so the migration guide asks the customer to keep a copy of the server image the tenant runs in their own registry and point the tenant at it.

## 5. OpenSearch

### 5.1 Single-step install (no separate operator)

Choose the OpenSearch admin password first. It must be the same value you later supply as `search.privilegedPassword` in values (normally your secret companion values file) or, from the first chart release after 0.2.7, as `SEARCH_INIT_PASSWORD` in the `eyelevel-secret-credentials` Secret. Supply it to OpenSearch through a Kubernetes Secret, so the password is not written into the OpenSearch StatefulSet pod spec where anyone who can read pods in the namespace could see it. Restrict permissions before each file exists, and create it in an editor rather than with a shell command so the password is not saved to your shell history. Run `umask 077` in your shell first, then create `opensearch-admin-secret.yaml` in an editor with this content, and confirm it is owner-only with `chmod 600 opensearch-admin-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: opensearch-admin
  namespace: eyelevel
type: Opaque
stringData:
  OPENSEARCH_INITIAL_ADMIN_PASSWORD: "<opensearch-admin-password>"
```

Apply the Secret, then delete the local `opensearch-admin-secret.yaml` file:

```bash
kubectl apply -f opensearch-admin-secret.yaml
```

Create `opensearch-admin.values.yaml`, which references the Secret instead of embedding the password, so this file holds no credential:

```yaml
extraEnvs:
  - name: OPENSEARCH_INITIAL_ADMIN_PASSWORD
    valueFrom:
      secretKeyRef:
        name: opensearch-admin
        key: OPENSEARCH_INITIAL_ADMIN_PASSWORD
```

Then install OpenSearch with both values files:

```bash
helm repo add opensearch https://opensearch-project.github.io/helm-charts/
helm repo update

helm install opensearch opensearch/opensearch -n eyelevel -f helm/values/opensearch/values.yaml -f opensearch-admin.values.yaml
```

Choose a password you have not published anywhere. From the first chart release after 0.2.7 the GroundX chart rejects a known published default for `search.password` or `search.privilegedPassword` given as a value and fails to render if you supply one (a Secret-delivered `SEARCH_PASSWORD` or `SEARCH_INIT_PASSWORD` is not render-validated, so never put a published default there either), so an upgrade that silently keeps the old default (for example `helm upgrade --reuse-values`) will not deploy. Published 0.2.7 and earlier do not reject it, so on those versions choose and set a new password yourself.

OpenSearch requires `OPENSEARCH_INITIAL_ADMIN_PASSWORD` at every start, not only on first initialization. On an already-initialized data volume it is still read at boot, and a start without it exits with `No custom admin password found` (observed on image digest `sha256:8e95a30f…`). Keep `-f opensearch-admin.values.yaml` on every `helm upgrade opensearch …`, not just the first install, and pin the OpenSearch image to a digest. The value is consumed only to initialize an empty volume; changing it on an existing volume does not rotate the stored admin password (rotate with the backup-based route in `upgrades.md`). The Secret must exist before OpenSearch starts, which the order above ensures.

Rotating these passwords does not by itself secure OpenSearch for production: the documented install still trusts OpenSearch's demo TLS certificates, and the GroundX application user has broad privileges. For production, also replace the demo certificates with operator-supplied ones and restrict network access to OpenSearch.

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
- From the first chart release after 0.2.7, no admin password is seeded (published 0.2.7 and earlier seed the public default): the seed file sets no `OPENSEARCH_INITIAL_ADMIN_PASSWORD`. The operator supplies it through a Kubernetes Secret referenced by `extraEnvs[].valueFrom.secretKeyRef` in § 5.1.

### 5.3 What the GroundX chart assumes

The chart's `groundx.search.serviceName` defaults to `opensearch`. The OpenSearch service lands at `opensearch-cluster-master.{namespace}.svc.cluster.local:9200` via the chart's standard naming pattern. Both `search.password` and `search.privilegedPassword` are needed from the first chart release after 0.2.7 whenever `mode` is not `ingest`, and both are operator-supplied by values or by the cluster credentials Secret (`SEARCH_PASSWORD`, `SEARCH_INIT_PASSWORD` in `eyelevel-secret-credentials`, listed in `cluster.secrets`; the Secret route needs the `groundx` and `process` images that the same chart release deploys by default (both log in to OpenSearch: the API to search, the indexing worker to write the index); if you override either with `groundx.image` or `process.image`, override both with images built from that chart release or later, and for a tag that is not a version number (such as `chainguard` or a mirrored tag) confirm with the image provider that both images read `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD`, or set `search.password` and `search.privilegedPassword` in values instead): that release has no default for either, while published 0.2.7 and earlier still ship the public default, so set both in values there (the Secret route does not apply on those versions). `search.privilegedPassword` (or `SEARCH_INIT_PASSWORD`) must equal the OpenSearch admin password supplied in § 5.1. `search.password` is a separate application credential and is not an OpenSearch seed value: the GroundX API provisions `search.username` with `search.password` at startup, authenticating with `search.privilegedUsername` / `search.privilegedPassword`. See `values-authoring.md` section 3.5.4 for the Mode 2 admin-password rule and the upgrade note.

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
  --version 0.2.7 \
  -n eyelevel
```

> **Brownfield 0.1.x Kafka must migrate first.** This `helm install` is the greenfield path and assumes no existing `groundx-strimzi-kafka-cluster` release. A cluster already running the **0.1.x** subchart is on the old `kafka.strimzi.io/v1beta2` API and must be converted to `v1` before any `0.2.7` install or upgrade: follow the chart's own "Upgrading an existing 0.1.x install" runbook (`prereqs/kafka-cluster/README.md` in groundx-on-prem: operator hop to Strimzi 0.50.1 dual-serving, `strimzi-v1-api-conversion` + CRD upgrade, then `helm upgrade` to 0.2.7). Running this `helm install` against an existing 0.1.x release fails, and a plain Strimzi rolling upgrade does not perform the v1beta2 -> v1 conversion.

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

For deployers running the GroundX chart with `imageType: chainguard`, the chart ships the Chainguard seed files below under `src/groundx/values/chainguard/`. No MinIO AIStor or OpenSearch Chainguard variant ships in the chart; deployer-supplied overrides are required for OpenSearch on Chainguard. The two MinIO files there are unchanged legacy seeds for the community MinIO operator and tenant, which this guide no longer installs:

| Subsystem | Chainguard seed file | What it does |
| --- | --- | --- |
| Community MinIO operator (legacy) | `values.minio.operator.yaml` | Unchanged legacy seed for the community MinIO operator. Pins operator image to `cgr.dev/eyelevel.ai/minio-operator-fips`. References `chainguard-pull-secret`. |
| Community MinIO tenant (legacy) | `values.minio.tenant.yaml` | Unchanged legacy seed for the community MinIO tenant. Pins tenant image to `cgr.dev/eyelevel.ai/minio-fips`. References `chainguard-pull-secret`. |
| Strimzi operator | `values.strimzi.operator.yaml` | Pins all Strimzi operator + worker images to `cgr.dev/eyelevel.ai/strimzi-kafka-operator` and `cgr.dev/eyelevel.ai/strimzi-kafka`. References `chainguard-pull-secret`. |
| Strimzi Kafka cluster | `values.strimzi.cluster.yaml` | Sets `node: eyelevel-cpu` and leaves the subchart cluster version (cluster.version) unset so Strimzi selects a supported default (the prior 4.1.0 pin is removed as of chart 0.2.7). Does **not** reference `chainguard-pull-secret` directly; the cluster CR inherits image-pull configuration from the Strimzi operator. |
| NVIDIA | `values.nvidia.yaml` | Sets `operator.runtimeClass: nvidia-container-runtime`. Does **not** override NVIDIA operator images — those come from the upstream NVIDIA registry. The Chainguard NVIDIA variant overlaps content-wise with the AKS-specific seed. |
| **OpenSearch** | None shipped | Deployers running OpenSearch on Chainguard must supply their own image overrides for the OpenSearch Helm chart. |
| **MinIO AIStor** | None shipped | The chart ships no Chainguard seed for the AIStor operator or object store. |

Layer the Chainguard seed onto the standard seed for each operator install: pass the standard values file first and the Chainguard seed second, each with `-f`.

The Strimzi operator Chainguard seed and the legacy community MinIO seeds reference `chainguard-pull-secret` for image-pull authentication; the deployer creates this secret in the install namespace before the install (see `image-variants.md` § 6). The Strimzi *cluster* and NVIDIA Chainguard seeds inherit their pull-secret configuration from the corresponding operator's release.

## 8. Renaming releases — propagating service-name overrides

The GroundX chart and each backing-service Helm release (the operator releases and the OpenSearch release) agree on service names. If a deployer renames either side, both must stay in sync:

| If you set... | …in the GroundX chart, the operator release must produce... |
| --- | --- |
| `db.serviceName: my-db` | Percona services at `my-db-cluster-haproxy.{ns}.svc.cluster.local` and `my-db-cluster-haproxy-replicas.{ns}.svc.cluster.local`. Typically: `helm install my-db-cluster percona/pxc-db` with `nameOverride: my-db-cluster`. |
| `file.serviceName: my-minio` | The chart then connects to `my-minio.{ns}.svc.cluster.local` and waits on `my-minio-tenant-hl.{ns}.svc.cluster.local` (§ 4.3). The on-prem README installs the AIStor object store only as `objectStore.name: minio-tenant`, which serves the default hosts for `file.serviceName: minio`, and gives no steps for another name. Keep both defaults, or connect a differently named store through `file.existing` (`service-substitution.md` § 4.3). |
| `search.serviceName: my-search` | OpenSearch master service at `my-search-cluster-master.{ns}.svc.cluster.local`. The OpenSearch Helm chart creates `{clusterName}-master`, so set `clusterName: my-search-cluster`. |
| `stream.serviceName: my-stream` | Strimzi bootstrap service at `my-stream-cluster-kafka-bootstrap.{ns}.svc.cluster.local`. Strimzi creates `{kafka-cr-name}-kafka-bootstrap`, so the `Kafka` CR must be named `my-stream-cluster` (in the `groundx-strimzi-kafka-cluster` release). |

Mismatch yields "no such host" errors in the GroundX pods' connection logs. Run `helm template` against both releases before install to verify the service names align.

## 9. Operator vs cluster — what depends on what

The Helm install ordering matters:

1. **NVIDIA GPU Operator first** if the deployment uses any GPU (most do). The operator's DaemonSet must register `nvidia.com/gpu` on the nodes before GroundX's inference pods can schedule.
2. **Percona operator + cluster** before the GroundX chart. The chart's pods wait for `db.rw` to be reachable (init containers) and fail to start if the Percona cluster isn't running.
3. **MinIO AIStor operator + object store** before the GroundX chart, with the license Secret `minio-license` created before the operator: without it the operator creates no object store (§ 4.1). Same wait pattern via the pre-process / extract / layout pods, which read from the object store.
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
