# Cluster Requirements

This file documents **what the underlying Kubernetes cluster has to provide** before GroundX can deploy onto it — chip architecture, GPU model class, GPU operator, Kubernetes / Helm versions, namespace expectations, persistent-volume class, and the rough cluster-wide CPU / memory / GPU budget for a vanilla deployment.

For per-microservice resource sizing and node-group targeting, route to `references/node-groups.md`. For backing-service prerequisites (existing MySQL vs operator-deployed Percona, etc.), route to `references/services-prereqs.md`.

## 1. CPU architecture

GroundX runs on **x86_64 / AMD64** nodes. The chart's container images are built for x86_64 and there is no published ARM64 / Graviton variant.

A deployer targeting AWS EKS should choose EC2 instance families backed by Intel or AMD x86 silicon (e.g., `m5`, `m6i`, `c5`, `c6i`, `r5`, `r6i` on the CPU side; `g4dn`, `g5`, `p4d`, `p4de` on the GPU side). Graviton (`m6g`, `c7g`, etc.) is **not** a supported target.

A deployer targeting Azure AKS should choose `D`-series / `E`-series / `F`-series for CPU nodes and `NC` / `NV` / `ND`-series for GPU nodes. ARM-based AKS node sizes are **not** a supported target.

## 2. GPUs

### 2.1 What's required

GroundX requires **NVIDIA CUDA-capable GPUs**. By default `layout-inference` and `ranker-inference` request `nvidia.com/gpu` via `resource.requests` / `resource.limits`. `summary-inference` does not request `nvidia.com/gpu` by default: it reaches its GPU through placement on the `eyelevel-gpu-summary` node group, so several summary copies can land on the same GPU. A GPU request can be added through `summary.inference.resources`. All three depend on the NVIDIA GPU Operator (or equivalent runtime configuration) to make the GPU usable.

Non-NVIDIA accelerators (AMD ROCm, Intel Gaudi, AWS Trainium / Inferentia, Google TPU) are **not** supported. The chart's CUDA-based container images do not run on them.

### 2.2 Per-microservice GPU memory minimums

| Inference microservice | GPU memory per worker+thread | Total per pod (assuming chart defaults) | Notes |
| --- | --- | --- | --- |
| `layout-inference` | ~2.5 GB | Scales with worker × thread; chart default `1×6` workers/threads | GPU is the default. CPU fallback is possible via `layout.inference.deviceType: cpu`, which auto-strips the `nvidia.com/gpu` request/limit for `layout-inference` (chart 0.2.7) — no manual `resource.limits`/`resource.requests` override needed for that part. Retargeting off the `eyelevel-gpu-layout` node group is a separate required step (`deviceType` alone does not move the pod) — see `references/values-authoring.md § 3.11`. |
| `ranker-inference` | ~1.25 GB | Chart-default `14×1` workers/threads gives a **~17.5 GB estimated footprint**; **24 GB is the recommended card class** (footprint plus headroom), not an inherent floor — a **T4 (16 GB)** runs `ranker-inference` at reduced worker/thread counts | CPU is unreliable. Plan for GPU. |
| `summary-inference` | `summary.inference.deviceUtilize` × the GPU's memory per worker (default 0.48) | **Sized for a 48 GB GPU.** The default runs 2 copies (`summary.inference.replicas.desired: 2`) of 1 worker each at `summary.inference.deviceUtilize: 0.48`, 0.96 of one GPU, and both copies share the summary GPU, because `summary-inference` requests no `nvidia.com/gpu` by default. One 24 GB GPU cannot run both copies; use the 24 GB values in § 2.3 | GPU **required**. Disable the microservice via `summary.api.enabled: false` + `summary.inference.enabled: false` (and point `summary-client` at an external LLM) if no GPU budget is available. |

For per-microservice worker / thread defaults and how they translate to replicas, route to `references/node-groups.md` § 4.

### 2.3 GPU model class

In practical terms, a vanilla deployment with all three GPU microservices needs at least:

- **One GPU for `summary-inference`.** The default summary values (2 copies × 1 worker × `summary.inference.deviceUtilize: 0.48`) are sized for a 48 GB GPU, such as the NVIDIA L40S on `g6e.xlarge` that the bundled Terraform provisions for `eyelevel-gpu-summary`. Because `summary-inference` requests no `nvidia.com/gpu` by default, both default copies share that one GPU, so one 24 GB GPU cannot run both: the second copy fails to load its model and never becomes Ready. On a 24 GB card use the single-copy values below. A T4 (16 GB) cannot host `summary-inference` at the default values.
- **One GPU for `ranker-inference`** — a **T4 (16 GB)** is viable at reduced worker/thread sizing. The chart's default `14×1` workers/threads count (~1.25 GB per worker/thread) gives an **estimated footprint of ~17.5 GB**; **24 GB is the recommended card class** for that default, providing headroom above the estimate. This is not an inherent 24 GB floor.
- **One GPU large enough for `layout-inference`** at the configured worker+thread count (often 16 GB+ is enough for `1×6`, but the deployer should multiply 2.5 GB × worker × thread).

These can be the same physical GPU (with MIG / time-slicing) or separate GPUs on separate nodes, but the chart's default `nodeSelector` separates them — see `references/node-groups.md`.

**Summary on one 24 GB GPU.** The summary GPU budget per node is copies (`summary.inference.replicas`) × workers (`summary.inference.workers`) × `summary.inference.deviceUtilize`, and it must stay at or below 1 for every summary GPU node; the defaults use 2 × 1 × 0.48 = 0.96 of a 48 GB card. For a single 24 GB summary GPU set:

```yaml
summary:
  inference:
    replicas:
      desired: 1
      min: 1
      max: 1
    workers: 1
    deviceUtilize: 0.9
    updateStrategy: Recreate
```

- One copy at `summary.inference.deviceUtilize: 0.48` does not fit either: on the tested card its first model load failed with no memory left for the KV cache and the copy started only through the summary worker's automatic retry at twice that value. At 0.9 it loads on the first attempt; do not rely on the retry.
- Apply it to a running install as an in-place `helm upgrade` that passes your existing values file and then this block as a second values file. `summary.inference.updateStrategy: Recreate` stops the old copy before the new one starts, so summary is down for the drain time plus model load on each upgrade that changes the summary pod (the drain applies on the 0.2.8 chart line and later; earlier charts can still cut off in-flight tasks; see `references/values-yaml.md` § 5.2).
- The values assume a dedicated summary GPU node with nothing else on its GPU.
- Tested on one NVIDIA A10G (`g5.2xlarge`, 1 GPU with 24 GB of GPU memory per https://aws.amazon.com/ec2/instance-types/g5/) with the chart-default image `summary-inference:0.2.7` and helm client v3.19.0. Other 24 GB cards, such as the NVIDIA L4, are untested.
- Recreate is also recommended for the 48 GB defaults: with the default rolling update a new copy starts before an old one stops, and on a GPU the running copies already fill it fails to load. That recommendation is derived from the rolling-update behavior and the 24 GB test, not tested on a 48 GB card. See `references/upgrades.md` § 8.
- With `cluster.hpa: true` or more than one summary GPU node, cap `summary.inference.replicas.max` and give each copy its own GPU through `summary.inference.resources`; see `references/autoscaling.md` § 8. Copies on more than one node also need ReadWriteMany storage for the summary model volume: every copy mounts the one `summary-model` claim, which follows `cluster.pvAccessMode` unless `summary.inference.pvc.access` overrides it, and a `ReadWriteOnce` claim mounts from one node only, so the second node's copy never starts. Set `summary.inference.pvc.access: ReadWriteMany` with a ReadWriteMany class in `summary.inference.pvc.class`, and on an existing install also a new `summary.inference.pvc.name`, because Kubernetes rejects a change to a bound claim's access mode (the model is downloaded again into the new claim). Do not change `cluster.pvAccessMode` on an existing install for this; it changes every chart claim that follows it and the upgrade fails. A fresh install may use either key. Without a ReadWriteMany class, keep summary on one node (see the single-replica ReadWriteOnce paragraph in § 5).

See `references/values-authoring.md § 3.3` for the same T4-viable-for-ranker guidance in the discovery questionnaire — the two files agree on this and must stay in sync.

**Host RAM (system memory, separate from VRAM).** A GPU node also needs host RAM above a per-group floor, independent of its GPU memory: `eyelevel-gpu-ranker` 30 GB, `eyelevel-gpu-layout` 12 GB, `eyelevel-gpu-summary` 30 GB — the RAM column of the Terraform README "Total Recommended Resources" (`terraform/groundx-operator/README.md`). A card with enough VRAM on an instance whose host RAM is below this floor can still OOM, so size both. This README citation is scoped to the RAM and disk columns. Only the README's ranker VRAM figure (gpu-ranker 16 GB) diverges from § 2.2, so do not import it; its gpu-summary 48 GB figure agrees with the summary sizing in § 2.2.

### 2.4 NVIDIA GPU Operator

The **NVIDIA GPU Operator** must be installed on the cluster *before* GroundX. The operator provides the device plugin (`nvidia.com/gpu` resource registration), the container runtime configuration, and the driver lifecycle. Without it, GroundX's inference pods schedule but fail to acquire GPUs.

For installation specifics (incl. the AKS-specific runtimeClass quirk), route to `references/gpu-operator.md`.

## 3. Kubernetes and Helm versions

### 3.1 Helm

- **Helm v3.8 or newer.** The chart uses Helm v3 features (no Tiller) and modern templating. Helm v2 is not supported.

### 3.2 Kubernetes

The chart does **not** pin a `kubeVersion` constraint in `Chart.yaml` — there is no hard lower bound enforced at install time. In practice, target a modern release: any Kubernetes version supported by the underlying cloud (AWS EKS, Azure AKS, Red Hat OpenShift) and recent enough to ship the NVIDIA Device Plugin / GPU Operator features GroundX depends on.

### 3.3 OpenShift

Red Hat OpenShift is a supported target. For the OpenShift AI quickstart deployment path, route to `references/openshift.md`.

## 4. Namespace

GroundX assumes it **owns its namespace**. Co-tenanting GroundX pods alongside unrelated workloads in the same namespace is not supported and not how the chart is designed.

The deployer chooses the namespace name and creates it before `helm install`. Common patterns:

- `groundx` (single-cluster, single-deployment).
- `groundx-prod` / `groundx-stage` / `groundx-dev` (lifecycle separation).
- Customer-named for managed deployments.

Per-customer namespace partitioning is **not** how multi-tenancy is enforced — customer isolation is enforced via owner-username tagging on stored artifacts. See `groundx-architecture/references/multi-tenancy.md`.

## 5. Persistent volumes

When backing services are deployed by the chart in operator-managed-dedicated mode (Mode 2: Percona MySQL, Strimzi Kafka, OpenSearch as a plain Helm release, MinIO AIStor operator, the in-cluster Redis), they request `PersistentVolumeClaim` resources against the cluster's **default `StorageClass`**.

The deployer must ensure the default `StorageClass`:

- Provisions volumes with **`ReadWriteOnce`** access (single-pod attachment is sufficient for every backing service the chart deploys).
- Provides **dynamic provisioning** (the chart does not pre-create PVs).
- Provides enough IOPS / throughput for the chosen backing-service load — production OpenSearch and Kafka especially benefit from SSD-backed storage classes (e.g., `gp3` on EKS, `managed-csi-premium` on AKS).

When backing services are in **existing customer-managed** mode (Mode 1) or **cloud-managed** mode (Mode 3), the chart does **not** request PVCs for them — the deployer's existing storage handles persistence.

**Single-replica ReadWriteOnce and ungraceful node loss.** The inference model-cache PVCs (`ranker-model` / `layout-model` / `summary-model`) follow `cluster.pvAccessMode`, which **defaults to `ReadWriteMany`** (EFS, the `setup-eks`-recommended default): a shared filesystem with no single-attachment stranding, so this caveat does not apply on the default path. On any access mode, a pod lost mid-download can leave a `downloading` lock that makes every new pod wait in Init indefinitely; on `ReadWriteMany`, clear it in place rather than replacing the claim, with the `ReadWriteMany` recovery below. The stranding caveat applies only when `pvAccessMode` is overridden to `ReadWriteOnce` (EBS block storage). On that path every replica of an inference service mounts the same claim, and an RWO claim can be mounted from only one node, so keep each inference service on one node (for example 1 replica with its HPA off; `summary.inference` defaults to 2 replicas) or use `ReadWriteMany` for replicas on more than one node. Each cache is then a single-replica RWO volume that can be **stranded or corrupted** when its node is lost ungracefully: it cannot detach cleanly, and a force-detach of a mounted ext4 volume mid-write can leave the filesystem inconsistent. **Confirm the old node is truly gone (terminated or fenced, not merely `NotReady`) before recovering**: a `NotReady` node may still be writing, and force-detaching a still-mounted volume can corrupt it. Then taint it `node.kubernetes.io/out-of-service=nodeshutdown:NoExecute` so the controller force-detaches the volume and force-deletes the stuck pod (remove the taint once the node is deleted). The cache is disposable, so replace it instead of reusing it, with the `ReadWriteOnce` recovery below: a reused cache can be corrupt, can carry a stale `complete.<version>` marker that makes `download-model` skip the download, or can carry a `downloading` lock left by a pod lost mid-download, which makes every new pod wait in Init indefinitely. See `references/services-prereqs.md` § 3.1.

**Model-cache recovery.** `references/services-prereqs.md` § 3.1 and `references/air-gapped.md` § 6.5 give the same order. Every path starts by scaling the inference Deployment (`layout-inference`, `ranker-inference` or `summary-inference` by default) to 0, which keeps replacement pods away: Kubernetes stops an HPA from acting on a Deployment scaled to 0. A `helm upgrade`, or a `terraform apply` that upgrades the GroundX release, renders the replica count again, so run neither until cleanup is done.

- **`ReadWriteMany`: clear the lock in place.** After scaling to 0, run `kubectl get pods -n <namespace> -l app=<inference-service>` until it returns no pods; the scale command returns before the pods stop. A pod left `Terminating` on a terminated or fenced node is cleared by the `out-of-service` taint above, or by force-deleting only that pod. Then, and only after that wait succeeds, start a short-lived pod that mounts the claim, and from it delete `complete.<version>`, any partial `*.tar.gz.part.*` files and the `downloading` lock, which sit at the root of the volume. Then delete the short-lived pod before you restore the replicas (scale back to the previous count, or re-run your `helm upgrade`).
- **`ReadWriteOnce`: replace the claim.** After scaling to 0, wait until no pod using the claim remains, with the same `kubectl get pods` check and `Terminating`-pod handling as the `ReadWriteMany` step above: while such a pod exists, even one left `Terminating` on the lost node, the claim is in use and its deletion does not finish. Only after that wait succeeds, delete the PVC, then wait until the deleted claim is gone, then re-run your `helm upgrade` with your original values. A claim that `kubectl get pvc` still lists, including one in `Terminating`, is not gone. The claim is a separate chart resource that the Deployment only mounts, so nothing recreates it on its own: the `helm upgrade` recreates the claim and restores the replicas, and `download-model` repopulates it as the pod starts.
- **Both paths: check the model works.** The init container's exit 0 and the `complete.<version>` marker do not prove the model is complete, because a failed download still writes the marker. Check the recovered service with its own test. For `summary-inference`, ingest a PDF with text per `install-flow.md` § 7.4 steps 1-3, then fetch that document's X-Ray (`GET /v1/ingest/document/xray/{documentId}`, or the document's `xrayUrl`; for the call shape, route to `groundx-api/`) and confirm its `fileSummary` is present and is not the literal `None`: an ingest status of complete and an empty `statusMessage` do not reveal summary failures. For `layout-inference`, the ingest completing (not `error`) is the check. For `ranker-inference`, the § 7.4 search must return the test document. Whichever check applies, if it fails, delete `complete.<version>` before retrying, using the `ReadWriteMany` order above so no pod using the claim can start while you do.

For a stateful backing-service PVC (Percona, OpenSearch, Kafka, MinIO) the data is authoritative. Each bundled store defaults to a single replica, and Percona, MinIO and Kafka all target the `eyelevel-cpu-only` node group, so several stores can share the lost node; for anything stateful, prefer a replicated backing service or HA-aware storage. The volume usually survives the node loss, so check it before discarding it. Confirm the lost node is terminated or fenced (not merely `NotReady`), and stop **every** stateful store with a pod on that node through its own documented procedure before any force-detach or `out-of-service` taint — the taint detaches every volume on the node, not only one store's. The bundled Kafka node pool sets `deleteClaim: true`, so Strimzi deletes a broker's PVC when it removes that Kafka node: never scale down or delete the `KafkaNodePool` (or the `Kafka` resource) during recovery. Pausing reconciliation (`strimzi.io/pause-reconciliation`) does not keep the broker stopped: Strimzi's pod controller still recreates a deleted broker pod on the same PVC within seconds. To keep Kafka stopped, scale the Strimzi operator to zero before the taint (`kubectl scale deployment strimzi-cluster-operator -n <operator-namespace> --replicas=0`; the bundled Terraform install runs it in the GroundX namespace, `eyelevel` by default). The scale command returns before the operator stops, and a still-running operator recreates the broker. If the operator was on the lost node, its pod can remain `Terminating` because the kubelet cannot finish deleting it. After scaling the Deployment to zero, confirm that pod's `spec.nodeName` is the terminated or fenced node, then force-delete only that stale operator pod (`kubectl delete pod <operator-pod> -n <operator-namespace> --force --grace-period=0`). Never force-delete an operator pod on an unfenced node. Operator pods on healthy nodes must terminate normally. Then wait until all operator pods are gone (`kubectl wait --for=delete pod -l name=strimzi-cluster-operator -n <operator-namespace> --timeout=180s`) before tainting, and confirm the broker pod does not come back once the taint removes it. While the operator is at zero, Strimzi manages none of the Kafka clusters it watches, and an upgrade or rollback of the operator's Helm release (including one a `terraform apply` makes when that release changes) restores its replica count, so make neither until the volume check is done. After the check, scale the operator back to its previous replica count (1 by default) and wait for the broker pod itself to be `Ready`: it can take up to about five minutes to reappear, and the `Kafka` resource can still report `Ready` while no broker is running. Check each detached volume before restarting its store. Restore from backup only if the volume is genuinely lost or unrecoverable; never recreate the PVC or restore an older backup over an intact volume — that discards writes since the backup. See GX-43 for the related rollout-deadlock and zone-locked-EBS exposure.

For per-service storage sizing and class recommendations, route to `references/services-prereqs.md`.

## 6. Cluster-wide resource budget (vanilla deployment)

A precise budget depends on workload (concurrent ingest rate, document size, summary-engine choice, autoscaling enabled / disabled). The rough envelope for a vanilla deployment with `summary.api.enabled: true` + `summary.inference.enabled: true`, all backing services in Mode 2, HPA off, no extraction, no workspace:

| Resource class | Approximate budget | Notes |
| --- | --- | --- |
| **CPU (orchestration tier)** | ~8–16 vCPU baseline | API + queue + pre-process + process + summary-client + metrics + layoutWebhook + groundx. Scales with throughput; HPA on multiplies this. |
| **CPU (layout pipeline non-inference)** | ~4–8 vCPU baseline | `layout-api`, `layout-process`, `layout-correct`, `layout-ocr` (Tesseract is CPU-heavy), `layout-map`, `layout-save`. |
| **CPU (ranker non-inference)** | ~1–2 vCPU | `ranker-api`. |
| **CPU (summary non-inference)** | ~1–2 vCPU | `summary-api`. |
| **Memory (orchestration + non-inference)** | ~32–64 GiB baseline | Scales with concurrent in-flight ingest jobs. `pre-process` and some `layout-*` sub-microservices need extra memory — see `references/node-groups.md` for the `eyelevel-cpu-memory` node-group profile. |
| **GPU memory (vision)** | ~2.5 GB × `layout-inference` worker × thread (default `1×6` ≈ 15 GB) | Card with at least that much memory required. |
| **GPU memory (ranker)** | ~17.5 GB estimated footprint at chart-default `14×1` sizing; provision a 24 GB card class | Not a floor — a T4 (16 GB) runs `ranker-inference` at reduced worker/thread counts. 17.5 GB is the computed footprint; 24 GB is the recommended card class with headroom. |
| **GPU memory (summary)** | A 48 GB card for the default 2 copies at `summary.inference.deviceUtilize: 0.48` | One 24 GB card only with the single-copy values in § 2.3. `summary.api.enabled: false` + `summary.inference.enabled: false` removes this requirement entirely. |
| **CPU (backing services, Mode 2)** | ~4–8 vCPU baseline | Sum across Percona, Redis, OpenSearch, MinIO AIStor, Strimzi. Production load needs more. |
| **Memory (backing services, Mode 2)** | ~16–32 GiB baseline | Same caveat. |
| **Persistent storage (backing services, Mode 2)** | 100s of GiB to TiBs | Driven by ingested document volume + retention. |

The numbers above are **rough planning baselines**, not commitments. They assume the chart's default replica counts and worker / thread settings. For the canonical resource modelling, the upstream `groundx-on-prem` repo's `bin/estimate` workflow is the source of truth — route to `references/cost-estimation.md` for the deployment-side framing of that workflow.

### 6.1 `layout-process` node ephemeral-disk sizing

On an image built from `ai-server` with the GX-61 change, `layout-process` pages render to disk instead of holding a whole batch in memory (see `references/values-yaml.md` § 5.2 for `layout.process.renderDiskBudgetMi`). The chart sizes each `layout-process` pod's ephemeral-storage request as `workers × threads × renderDiskBudgetMi + 1024` MiB — 3072Mi at the chart's `layout.process` defaults (1 worker × 1 thread, `renderDiskBudgetMi: 2048`) — regardless of which image is deployed; an older image ignores the render-disk budget and renders each batch in memory instead.

Node ephemeral-disk budget for `layout-process` must cover that per-pod request multiplied by the number of `layout-process` pods a node schedules, plus the `layout-process` image size. A larger `renderDiskBudgetMi`, or more `layout.process` workers or threads, scales the per-pod request linearly — recompute the node budget from the formula above rather than reusing the 3072Mi default figure whenever any of those three inputs changes.

### 6.2 Node root/ephemeral-disk sizing

A node's root/ephemeral disk is separate from GPU VRAM (§ 2) and from backing-service PVC sizing (§ 5), and it is what the § 6.1 `layout-process` ephemeral budget is consumed from. On the bundled Terraform path, `eks.tf` provisions each node's root volume as `max(deployment_type.min_pv, nodes.node_groups.<group>_nodes.ebs.volume_size)`. `min_pv` defaults to 20, so each group boots at its per-group `ebs.volume_size` default (CPU 30, GPU layout/ranker 75, GPU summary 100 GiB — field values, not a guaranteed node size); the bundled `setup-eks` raises `min_pv` to 120 only on the chainguard-tagged image path, where every group's effective root disk is at least 120 GiB (larger if its `volume_size` is larger). For nodes provisioned by your own method, use the Terraform README "Total Recommended Resources" disk column as the recommendation: cpu-only 80, cpu-memory 20, gpu-layout 35, gpu-ranker 75, gpu-summary 100 GB. Size the root disk to cover the § 6.1 `layout-process` ephemeral budget plus image sizes, not just the defaults above.

## 7. What this file does not cover

- **Per-microservice resource requests / limits** → `references/node-groups.md`.
- **Backing-service field-by-field selection** (`db.existing.*`, `cache.existing.*`, etc.) → `references/services-prereqs.md`.
- **Field-by-field `values.yaml` reference** → `references/values-yaml.md`.
- **NVIDIA GPU Operator install** → `references/gpu-operator.md`.
- **Terraform AWS EKS provisioning** → `references/terraform-aws.md`.
- **Red Hat OpenShift AI quickstart** → `references/openshift.md`.
- **Air-gapped image mirroring** → `references/air-gapped.md`.
- **Cost estimation via `bin/estimate`** → `references/cost-estimation.md`.
- **Architectural rationale for the GPU mix** → `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.
