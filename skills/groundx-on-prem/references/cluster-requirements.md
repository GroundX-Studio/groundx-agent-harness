# Cluster Requirements

This file documents **what the underlying Kubernetes cluster has to provide** before GroundX can deploy onto it — chip architecture, GPU model class, GPU operator, Kubernetes / Helm versions, namespace expectations, persistent-volume class, and the rough cluster-wide CPU / memory / GPU budget for a vanilla deployment.

For per-microservice resource sizing and node-group targeting, route to `references/node-groups.md`. For backing-service prerequisites (existing MySQL vs operator-deployed Percona, etc.), route to `references/services-prereqs.md`.

## 1. CPU architecture

GroundX runs on **x86_64 / AMD64** nodes. The chart's container images are built for x86_64 and there is no published ARM64 / Graviton variant.

A deployer targeting AWS EKS should choose EC2 instance families backed by Intel or AMD x86 silicon (e.g., `m5`, `m6i`, `c5`, `c6i`, `r5`, `r6i` on the CPU side; `g4dn`, `g5`, `p4d`, `p4de` on the GPU side). Graviton (`m6g`, `c7g`, etc.) is **not** a supported target.

A deployer targeting Azure AKS should choose `D`-series / `E`-series / `F`-series for CPU nodes and `NC` / `NV` / `ND`-series for GPU nodes. ARM-based AKS node sizes are **not** a supported target.

## 2. GPUs

### 2.1 What's required

GroundX requires **NVIDIA CUDA-capable GPUs**. The chart's inference pods (`layout-inference`, `ranker-inference`, `summary-inference`) request `nvidia.com/gpu` resources via `resource.requests` / `resource.limits` and depend on the NVIDIA GPU Operator (or equivalent runtime configuration) to make those resources schedulable.

Non-NVIDIA accelerators (AMD ROCm, Intel Gaudi, AWS Trainium / Inferentia, Google TPU) are **not** supported. The chart's CUDA-based container images do not run on them.

### 2.2 Per-microservice GPU memory minimums

| Inference microservice | GPU memory per worker+thread | Total per pod (assuming chart defaults) | Notes |
| --- | --- | --- | --- |
| `layout-inference` | ~2.5 GB | Scales with worker × thread; chart default `1×6` workers/threads | GPU is the default. CPU fallback is possible but requires explicit override of `resource.limits` and `resource.requests` to drop the `nvidia.com/gpu` request. |
| `ranker-inference` | ~1.25 GB | Sized for a **24 GB** GPU; chart default `14×1` workers/threads | CPU is unreliable. Plan for GPU. |
| `summary-inference` | ~12 GB | **24 GB total** sized for `1×1` workers/threads with Gemma 3 | GPU **required**. Disable the microservice via `summary.api.enabled: false` + `summary.inference.enabled: false` (and point `summary-client` at an external LLM) if no GPU budget is available. |

For per-microservice worker / thread defaults and how they translate to replicas, route to `references/node-groups.md` § 4.

### 2.3 GPU model class

In practical terms, a vanilla deployment with all three GPU microservices needs at least:

- **One GPU large enough for `summary-inference`** (24 GB of GPU memory) — e.g., NVIDIA L4, A10, A10G, A100 40 GB / 80 GB, H100. Smaller cards (T4 16 GB) cannot host `summary-inference` at default sizing.
- **One GPU large enough for `ranker-inference`** (also sized for 24 GB).
- **One GPU large enough for `layout-inference`** at the configured worker+thread count (often 16 GB+ is enough for `1×6`, but the deployer should multiply 2.5 GB × worker × thread).

These can be the same physical GPU (with MIG / time-slicing) or separate GPUs on separate nodes, but the chart's default `nodeSelector` separates them — see `references/node-groups.md`.

### 2.4 NVIDIA GPU Operator

The **NVIDIA GPU Operator** must be installed on the cluster *before* GroundX. The operator provides the device plugin (`nvidia.com/gpu` resource registration), the container runtime configuration, and the driver lifecycle. Without it, GroundX's inference pods schedule but fail to acquire GPUs.

For installation specifics (incl. the AKS-specific runtimeClass quirk), route to `references/gpu-operator.md` (planned). Until that file ships, the upstream NVIDIA GPU Operator documentation is the source of truth.

## 3. Kubernetes and Helm versions

### 3.1 Helm

- **Helm v3.8 or newer.** The chart uses Helm v3 features (no Tiller) and modern templating. Helm v2 is not supported.

### 3.2 Kubernetes

The chart does **not** pin a `kubeVersion` constraint in `Chart.yaml` — there is no hard lower bound enforced at install time. In practice, target a modern release: any Kubernetes version supported by the underlying cloud (AWS EKS, Azure AKS, Red Hat OpenShift) and recent enough to ship the NVIDIA Device Plugin / GPU Operator features GroundX depends on.

### 3.3 OpenShift

Red Hat OpenShift is a supported target. For the OpenShift AI quickstart deployment path, route to `references/openshift.md` (planned).

## 4. Namespace

GroundX assumes it **owns its namespace**. Co-tenanting GroundX pods alongside unrelated workloads in the same namespace is not supported and not how the chart is designed.

The deployer chooses the namespace name and creates it before `helm install`. Common patterns:

- `groundx` (single-cluster, single-deployment).
- `groundx-prod` / `groundx-stage` / `groundx-dev` (lifecycle separation).
- Customer-named for managed deployments.

Per-customer namespace partitioning is **not** how multi-tenancy is enforced — customer isolation is enforced via owner-username tagging on stored artifacts. See `groundx-architecture/references/multi-tenancy.md`.

## 5. Persistent volumes

When backing services are deployed by the chart in operator-managed-dedicated mode (Mode 2 — Percona MySQL, Strimzi Kafka, OpenSearch operator, MinIO operator, the in-cluster Redis), they request `PersistentVolumeClaim` resources against the cluster's **default `StorageClass`**.

The deployer must ensure the default `StorageClass`:

- Provisions volumes with **`ReadWriteOnce`** access (single-pod attachment is sufficient for every backing service the chart deploys).
- Provides **dynamic provisioning** (the chart does not pre-create PVs).
- Provides enough IOPS / throughput for the chosen backing-service load — production OpenSearch and Kafka especially benefit from SSD-backed storage classes (e.g., `gp3` on EKS, `managed-csi-premium` on AKS).

When backing services are in **existing customer-managed** mode (Mode 1) or **cloud-managed** mode (Mode 3), the chart does **not** request PVCs for them — the deployer's existing storage handles persistence.

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
| **GPU memory (ranker)** | ~24 GB | Card with at least 24 GB memory required. |
| **GPU memory (summary)** | ~24 GB | Card with at least 24 GB memory required. `summary.api.enabled: false` + `summary.inference.enabled: false` removes this requirement entirely. |
| **CPU (backing services, Mode 2)** | ~4–8 vCPU baseline | Sum across Percona, Redis, OpenSearch, MinIO, Strimzi. Production load needs more. |
| **Memory (backing services, Mode 2)** | ~16–32 GiB baseline | Same caveat. |
| **Persistent storage (backing services, Mode 2)** | 100s of GiB to TiBs | Driven by ingested document volume + retention. |

The numbers above are **rough planning baselines**, not commitments. They assume the chart's default replica counts and worker / thread settings. For the canonical resource modelling, the upstream `groundx-on-prem` repo's `bin/estimate` workflow is the source of truth — route to `references/cost-estimation.md` (planned) for the deployment-side framing of that workflow.

## 7. What this file does not cover

- **Per-microservice resource requests / limits** → `references/node-groups.md`.
- **Backing-service field-by-field selection** (`db.existing.*`, `cache.existing.*`, etc.) → `references/services-prereqs.md`.
- **Field-by-field `values.yaml` reference** → `references/values-yaml.md` (planned).
- **NVIDIA GPU Operator install** → `references/gpu-operator.md` (planned).
- **Terraform AWS EKS provisioning** → `references/terraform-aws.md` (planned).
- **Red Hat OpenShift AI quickstart** → `references/openshift.md` (planned).
- **Air-gapped image mirroring** → `references/air-gapped.md` (planned).
- **Cost estimation via `bin/estimate`** → `references/cost-estimation.md` (planned).
- **Architectural rationale for the GPU mix** → `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.
