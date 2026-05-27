# NVIDIA GPU Operator — Install Deep-Dive

This file documents **the NVIDIA GPU Operator install in detail** — what it provides, the AKS-specific `runtimeClass: nvidia-container-runtime` variant, OpenShift differences, driver version pinning, MIG / time-slicing for GPU sharing, and the failure modes specific to the GPU Operator path.

For the high-level overview and standard install command, route to `services-operators.md` § 2. For per-microservice GPU memory minimums, route to `cluster-requirements.md` § 2. For per-pod GPU-cost levers, route to `cost-estimation.md` § 3.

## 1. What the GPU Operator does

The NVIDIA GPU Operator is a Helm release that installs, on every GPU node:

- **NVIDIA Driver** — kernel module + userspace libraries.
- **NVIDIA Container Toolkit** — runtime hook so containerd / CRI-O can launch GPU-aware containers.
- **Device Plugin** — registers `nvidia.com/gpu` as a schedulable Kubernetes resource.
- **DCGM Exporter** (optional) — GPU metrics for Prometheus.
- **MIG Manager** (optional) — partitions a single physical GPU into multiple smaller logical GPUs.

Without the operator, GroundX's three inference deployments (`layout-inference`, `ranker-inference`, `summary-inference`) **schedule onto GPU nodes but fail to acquire GPUs** — `nvidia.com/gpu` resource registrations don't exist, and `nvidia-smi` inside containers returns no device.

## 2. The canonical install

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

The GroundX seed at `helm/values/nvidia/values.yaml` is deliberately thin:

```yaml
operator:
  runtimeClass: nvidia
```

That's the entire seed. Real installs typically add: a pinned driver version (see § 5), a tolerations block for GPU node taints, and operator features per the upstream NVIDIA docs.

## 3. AKS variant — `runtimeClass: nvidia-container-runtime`

On Azure AKS, the GPU node pool uses a different containerd runtime class name. The GroundX chart ships an AKS-specific seed:

```yaml
# helm/values/nvidia/values.aks.yaml
operator:
  runtimeClass: nvidia-container-runtime
```

Install with:

```sh
helm install nvidia-gpu-operator nvidia/gpu-operator \
  -n nvidia-gpu-operator \
  --create-namespace \
  --atomic \
  -f helm/values/nvidia/values.aks.yaml
```

**Why the difference.** AKS pre-installs an `nvidia-container-runtime` containerd runtime class on GPU node pools (the `NVIDIA Driver Installer` daemon set is also pre-deployed by Azure). The standard `runtimeClass: nvidia` doesn't exist on AKS; using it produces pods stuck in `ContainerCreating` with `failed to create containerd container: get runtime: no runtime for "nvidia" is configured`.

GKE has its own conventions (no operator install needed — GPU drivers are managed by GKE). EKS uses the generic `runtimeClass: nvidia` from the operator install.

## 4. OpenShift variant

On Red Hat OpenShift, the GPU Operator install differs in two ways:

1. **Use the Red Hat OperatorHub** to install the NVIDIA GPU Operator, not Helm. OpenShift's OLM (Operator Lifecycle Manager) is the canonical install path.
2. **Install the NVIDIA Node Feature Discovery operator first**, then the GPU Operator. NFD detects GPU presence on nodes; the GPU Operator then provisions the driver/runtime on flagged nodes.

The chart's `cluster.type: openshift` flag doesn't affect the operator install — operator install is out-of-band. But the chart's `groundx.isOpenshift` helper (`_helpers/main.tpl:108–111`) does branch on this in other ways (see `openshift.md`).

For the OpenShift AI quickstart deployment, route to `openshift.md`.

## 5. Driver version pinning

The GPU Operator can either:

- **Manage the driver** (default) — the operator installs and updates the NVIDIA driver on each GPU node. The deployer pins the driver version via `driver.version: 535.183.06` (or whatever Linux kernel + container runtime stack supports).
- **Use pre-installed driver** — when the cluster's nodes already ship with a driver (AKS GPU nodes, EKS optimized GPU AMIs), set `driver.enabled: false`. The operator only installs the device plugin + container toolkit.

The choice matters for reproducibility (managed driver is locked to a version) vs node-image alignment (pre-installed is faster to update via node-pool rolling).

```yaml
# operator-managed driver, pinned version
driver:
  enabled: true
  version: 535.183.06

# OR pre-installed driver
driver:
  enabled: false
```

Confirm via `kubectl logs -n nvidia-gpu-operator <driver-daemonset-pod>` or `kubectl get clusterpolicy` after install.

## 6. MIG / time-slicing — GPU sharing

A single physical GPU (typically an A100 or H100) can host multiple GroundX inference workloads simultaneously via:

### 6.1 MIG (Multi-Instance GPU)

A100 80GB and H100 80GB support **MIG partitioning** — a single GPU is split into multiple smaller GPUs (e.g., 7×10GB instances on A100 80GB, or 3×40GB instances). Each MIG instance is exposed as a separate `nvidia.com/gpu` resource.

For GroundX, MIG lets one A100 80GB host `layout-inference` (15GB instance), `ranker-inference` (24GB instance), and `summary-inference` (24GB instance) simultaneously — instead of three separate GPU nodes.

```yaml
mig:
  strategy: single   # or "mixed" for heterogeneous instance shapes
```

Per-node MIG configuration goes through a `ConfigMap` referenced by the operator. See the upstream NVIDIA MIG docs for the configuration shape.

### 6.2 Time-slicing

For GPUs that don't support MIG (T4, L4, A10), the operator can configure **time-slicing** — multiple containers share a GPU via context switching. Lower performance than MIG but works on more hardware.

```yaml
devicePlugin:
  config:
    name: time-slicing-config
    create: true
```

Time-slicing is appropriate when GroundX inference workloads are bursty and would otherwise leave the GPU idle. Not appropriate for steady-state high-throughput workloads where the context-switch overhead dominates.

## 7. Failure modes specific to GPU Operator

### 7.1 Pods schedule but `nvidia-smi` returns no device

**Cause.** Driver DaemonSet failed on the GPU node. Common reasons: kernel version mismatch with the driver version, secure boot enabled (signed-driver requirement), node missing kernel headers.

**Fix.** `kubectl -n nvidia-gpu-operator logs <driver-pod>` shows the failure. For kernel mismatches, pin a different `driver.version`. For secure boot, either disable or use NVIDIA's signed-driver path.

### 7.2 `nvidia.com/gpu` resource not registered on nodes

**Cause.** Device plugin DaemonSet failed or wasn't scheduled. NFD didn't tag the node as GPU-capable. Or the runtime class doesn't match the node's containerd config.

**Fix.** `kubectl get node <gpu-node> -o jsonpath='{.status.allocatable}'` should show `nvidia.com/gpu`. If absent, check `kubectl -n nvidia-gpu-operator get pods` for device-plugin failures. On AKS, confirm `runtimeClass: nvidia-container-runtime` (not the generic `nvidia`).

### 7.3 `Failed to start container: ... unknown runtime type "nvidia"`

**Cause.** Pod requested `nvidia.com/gpu` and the containerd runtime class is misnamed (AKS expects `nvidia-container-runtime`, others expect `nvidia`).

**Fix.** Use the right operator values file for the cloud (`values.yaml` for EKS/generic, `values.aks.yaml` for Azure). Verify via `kubectl get runtimeclass`.

### 7.4 MIG partitions don't appear

**Cause.** GPU doesn't support MIG (T4, L4, A10 are non-MIG), or MIG config wasn't applied at the operator level, or the node-level `nvidia.com/mig.config` annotation is missing.

**Fix.** Confirm GPU is MIG-capable: A100, H100 (80GB variants). Check operator's `mig` block and per-node MIG ConfigMap.

## 8. Verification post-install

```sh
# Operator is healthy
kubectl -n nvidia-gpu-operator get pods

# nvidia.com/gpu resource is registered on each GPU node
kubectl get node <gpu-node> -o jsonpath='{.status.allocatable}' | jq

# Container can see the GPU
kubectl -n eyelevel exec -it layout-inference-xxx -- nvidia-smi

# DCGM exporter (if enabled) is producing metrics
kubectl -n nvidia-gpu-operator port-forward svc/nvidia-dcgm-exporter 9400:9400
curl http://localhost:9400/metrics | head
```

If `nvidia-smi` returns a device but GroundX inference pods can't acquire it, check the `resource.limits` block in the rendered Deployment — `nvidia.com/gpu: 1` must be present.

## 9. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| Generic install on AKS without `values.aks.yaml` | `runtimeClass: nvidia` doesn't exist on AKS — pods fail to start. Use the AKS variant. |
| `driver.enabled: false` on a node without a pre-installed driver | Device plugin fails to bind; `nvidia.com/gpu` doesn't register. Either install the driver out-of-band or set `driver.enabled: true`. |
| MIG enabled on a non-MIG-capable GPU | Operator logs a warning; falls back to whole-GPU scheduling. Check `nvidia-smi -L` on the node to confirm MIG capability. |
| Time-slicing + steady high-throughput GroundX workload | Context-switch overhead degrades inference latency. Prefer dedicated GPUs or MIG for steady workloads. |
| GPU Operator not installed before the GroundX chart | GroundX inference pods schedule but stay `ContainerCreating` with `nvidia.com/gpu` resource error. Install the operator first (`install-flow.md`). |

## 10. What this file does not cover

- **Generic services-operators install pattern (the one-liner)** → `services-operators.md` § 2.
- **Per-microservice GPU memory minimums** → `cluster-requirements.md` § 2.2.
- **Cost levers (disable summary-inference, MIG-share, right-size layout workers)** → `cost-estimation.md` § 3.
- **OpenShift AI quickstart end-to-end deployment** → `openshift.md`.
- **GPU metrics in Prometheus / Grafana** → `monitoring.md`.
- **Per-cloud GPU instance recommendations** → `deployment-options.md` (planned) and `terraform-aws.md` (planned).
- **NVIDIA proprietary feature flags** (e.g., NVIDIA AI Enterprise licensing) → consult NVIDIA documentation.
- **Air-gapped GPU Operator install** → `air-gapped.md` (planned).
