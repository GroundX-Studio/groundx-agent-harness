# Node Groups

This file documents the **five `eyelevel-*` node-group labels** the GroundX Helm chart targets by default, the workload profile of each group, the chart's per-microservice worker / thread defaults, and how a deployer overrides the labels to fit a custom node-group naming scheme.

For chip architecture, GPU model class, GPU operator, and cluster-wide budget, route to `references/cluster-requirements.md`.

## 1. The five `eyelevel-*` labels

Every GroundX pod ships with a `nodeAffinity` block + matching `tolerations` block that targets one of five node-group label **values**:

| Default label value | Workload profile | Microservices targeted by default |
| --- | --- | --- |
| `eyelevel-cpu-only` | General CPU work, baseline memory | API + orchestration tier (`groundx`, `upload`, `queue`, `process`, `summary-client`, `metrics`, `layoutWebhook`), most non-inference layout sub-microservices, `ranker-api`, `summary-api`, `extract-api`, `workspace-api` |
| `eyelevel-cpu-memory` | CPU + extra memory headroom | CPU microservices that need additional memory beyond the baseline (e.g., `pre-process` workers and certain layout sub-microservices); the deployer assigns by per-microservice `node:` field in values.yaml |
| `eyelevel-gpu-layout` | GPU for the vision model | `layout-inference` |
| `eyelevel-gpu-ranker` | GPU for the re-ranker | `ranker-inference` |
| `eyelevel-gpu-summary` | GPU for the bundled summary stack | `summary-inference` (only when `summary.api.enabled: true` + `summary.inference.enabled: true`) |

The chart looks for these values under the node-label **key `eyelevel_node`** on the cluster's nodes. Apply `eyelevel_node=<value>` as a node label on each node group / node pool. The Terraform AWS EKS scaffolding in the upstream `groundx-on-prem` repo creates EKS managed node groups labeled accordingly — see `references/terraform-aws.md` (planned). On Azure AKS / generic Kubernetes / OpenShift, the deployer applies the labels themselves to whatever node-group or machine-pool abstraction the platform uses.

> **Don't use the bare key `node` for these labels.** `node` collides with reserved metric labels in Prometheus / Grafana and other Kubernetes-native observability stacks, and using it here can corrupt dashboards and alerts. Use `eyelevel_node` instead. (The chart's `nodeAffinity` template includes a second `matchExpressions` term for the key `node` as a legacy fallback; it works, but is discouraged for the reasons above and should not be relied on.)

The corresponding **tolerations** are also chart-default. The chart emits a toleration for `eyelevel_node=<value>:NoSchedule`, so a deployer who taints node groups with that key gets schedulability for the matching GroundX pods while keeping other workloads off.

### 1.1 Overriding the default values

The five label values are configurable via the `cluster.nodeLabels` block in values.yaml:

```yaml
cluster:
  nodeLabels:
    cpuMemory: eyelevel-cpu-memory   # default
    cpuOnly:   eyelevel-cpu-only     # default
    gpuLayout: eyelevel-gpu-layout   # default
    gpuRanker: eyelevel-gpu-ranker   # default
    gpuSummary: eyelevel-gpu-summary # default
```

Override any of these to match an existing label-value scheme. The key (`eyelevel_node`) is not configurable through values.yaml — it is baked into the chart's `nodeAffinity` and `tolerations` templates. To use a different key entirely, override per microservice with a custom `nodeSelector:` block (see § 4).

## 2. Why the GPU groups are separate

A deployer might reasonably ask why `eyelevel-gpu-layout` / `eyelevel-gpu-ranker` / `eyelevel-gpu-summary` are three distinct labels rather than one `eyelevel-gpu` umbrella. The reasons:

- **Different GPU memory profiles.** `summary-inference` needs ~24 GB per pod (Gemma 3). `ranker-inference` needs ~24 GB worth of worker × thread scheduling. `layout-inference` scales with worker count (`~2.5 GB × worker × thread`) and can be much smaller. Pinning the right card class to the right workload is materially easier with separate node groups.
- **Different scaling behaviors.** The layout vision model, the re-ranker, and the summary LLM have different concurrency, latency, and queue-depth profiles. Separate node groups let the deployer scale each axis independently.
- **Different cost levers.** A deployer with no on-prem summary requirement can disable both `summary.api.enabled` and `summary.inference.enabled` and never provision `eyelevel-gpu-summary` nodes at all — the biggest single GPU cost driver disappears. Keeping the labels distinct makes the toggle clean.

For architectural rationale on the three GPU workloads, route to `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.

## 3. Per-microservice worker / thread defaults

The chart sets per-microservice **worker** and **thread** counts in `values.yaml`. Each microservice has a `workers` field and a `threads` field; the inference pods' GPU sizing is in terms of `worker × thread`.

The chart defaults for the three inference microservices (from the upstream `groundx-on-prem` repo's per-microservice template-helper files under `templates/_helpers/app/`):

| Microservice | Default workers | Default threads | GPU memory per worker+thread | Default GPU memory footprint per pod |
| --- | --- | --- | --- | --- |
| `layout-inference` | 1 | 6 | ~2.5 GB | ~15 GB |
| `ranker-inference` | 14 | 1 | ~1.25 GB | ~17.5 GB (sized for 24 GB) |
| `summary-inference` | 1 | 1 | ~12 GB | ~12 GB (sized for 24 GB Gemma 3) |

Per-pod replica counts (`replicas:` in values.yaml) are 1 by default for each. Autoscaling (HPA) is **off** by default and turning it on multiplies the resource footprint by the autoscaler's max-replicas. See `references/autoscaling.md` (planned).

For the CPU + memory resource requests / limits per microservice (not GPU memory — Kubernetes-level CPU and memory `requests` and `limits`), the upstream `values.yaml`'s per-microservice block is the source of truth. The chart sets reasonable per-pod CPU + memory defaults; deployers tune them based on observed load.

## 4. Custom node-group labels — how to override

A deployer running on infrastructure where the `eyelevel-*` labels don't map cleanly (e.g., an existing Karpenter / Cluster Autoscaler scheme, OpenShift machine pools with different conventions, an air-gapped cluster with a custom taxonomy) overrides them via the per-microservice `node` block in `values.yaml`.

The override surface is large — there are roughly **20 microservice-level `node` blocks**, one per microservice that ships with a `nodeSelector`. The pattern, abstractly:

```yaml
# values.yaml override pattern
<microservice>:
  node:
    selector: <key>: <value>     # overrides the default eyelevel-* selector
    tolerations:                 # overrides the default taint toleration
      - key: <key>
        operator: <op>
        value: <value>
        effect: <effect>
```

The deployer overrides per-microservice rather than globally. There is **no single chart-level `globalNodeGroupPrefix`** — the chart was designed to let a deployer place each microservice independently.

For the field-by-field enumeration of every `node` block (one under each of `groundx`, `upload`, `queue`, `process`, `summaryClient`, `metrics`, `layoutWebhook`, `layoutApi`, `layoutProcess`, `layoutCorrect`, `layoutInference`, `layoutOcr`, `layoutMap`, `layoutSave`, `rankerApi`, `rankerInference`, `summaryApi`, `summaryInference`, the extract microservices, and the workspace microservices), the upstream `groundx-on-prem` repo's `values.yaml` is the source of truth — also captured in the upstream README's nodeSelector inventory.

The full mapping will land in `references/values-yaml.md` (planned) once that file ships.

## 5. Practical layout — minimum vs production

### 5.1 Minimum viable

The smallest viable cluster for a vanilla deployment (`summary.api.enabled: true` + `summary.inference.enabled: true`, all three GPU microservices):

- 1 × `eyelevel-cpu-only` node (multi-core, ~16–32 GB RAM) for orchestration + non-inference pods.
- 1 × `eyelevel-cpu-memory` node (multi-core, more RAM) for `pre-process` and memory-hungry layout sub-microservices.
- 1 × `eyelevel-gpu-layout` node with enough GPU memory for the default `1×6` worker+thread layout-inference (~16 GB+).
- 1 × `eyelevel-gpu-ranker` node with a 24 GB GPU.
- 1 × `eyelevel-gpu-summary` node with a 24 GB GPU (sufficient for Gemma 3).

The same physical GPU node can serve multiple node-group labels if the deployer is willing to MIG-partition the card or co-schedule with care, but this is **not** how the chart is shipped — the default pattern is one node group per label.

### 5.2 Production

Production sizing is workload-driven. Key levers:

- **HPA on.** Each inference pod scales horizontally; budget for `max-replicas × per-replica-cost` per GPU label.
- **`summary.api.enabled: false` + `summary.inference.enabled: false`.** Removes the `eyelevel-gpu-summary` node group entirely. Document content then leaves the cluster on each summary call — see `architecture.md` § 3.3.
- **Extract / workspace.** When `extract.enabled=true` or `workspace.enabled=true`, the corresponding microservices need a CPU-tier node group (default `eyelevel-cpu-only`).
- **Backing services.** Operator-deployed Percona / OpenSearch / Kafka / MinIO consume their own CPU + memory + storage budgets. See `references/services-prereqs.md`. These typically land on `eyelevel-cpu-only` or `eyelevel-cpu-memory` (deployer's choice, configured via their own operator's CRDs).

For total cluster-wide budget framing, route to `references/cluster-requirements.md` § 6.

## 6. What this file does not cover

- **Chip architecture, Kubernetes / Helm versions, namespace, PV class, cluster-wide budget** → `references/cluster-requirements.md`.
- **Backing-service prerequisites and selection mechanics** → `references/services-prereqs.md`.
- **Field-by-field `values.yaml` reference (including every `node` block)** → `references/values-yaml.md` (planned).
- **Autoscaling — HPA configuration, custom metrics server, per-pod scaling behavior** → `references/autoscaling.md` (planned).
- **NVIDIA GPU Operator install** → `references/gpu-operator.md` (planned).
- **Terraform AWS EKS managed node groups** → `references/terraform-aws.md` (planned).
- **Architectural rationale for the GPU workloads** → `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.
