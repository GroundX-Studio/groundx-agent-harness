# Cost Estimation

This file documents **what drives the cost of running GroundX on-prem and how to derive a per-deployment estimate** — the cost-relevant chart knobs, where cost concentrates across the five `eyelevel-*` node groups, and the manual sizing pattern (values.yaml plus an external pricing source).

GroundX is a **cloud-agnostic Helm chart**. There is no canonical cost-estimation tool inside the chart itself; cost modelling is a deployer responsibility done against the cluster's underlying compute and storage pricing (cloud-provider line items, on-prem capacity costs, etc.). The chart's contribution is exposing per-microservice `replicas` and `resources` in `values.yaml` so the deployer can sum them.

For per-microservice resource defaults and node-group targets, route to `node-groups.md`. For cluster-wide minimums and GPU model classes, route to `cluster-requirements.md`. For the decision between chart-deployed vs cloud-managed backing services (which materially shifts cost), route to `service-substitution.md`. For the architectural cost picture, route to `groundx-architecture/references/data-residency.md` and `groundx-architecture/references/disaster-recovery.md`.

## 1. The manual sizing pattern

The chart's `src/groundx/values.yaml` is the source of truth for per-microservice CPU / memory / replica defaults. To estimate cluster capacity:

1. Render the merged values (chart defaults + your overrides): `helm template groundx ./src/groundx -f my-overrides.yaml > rendered.yaml`.
2. For each microservice (`groundx`, `layout.*`, `extract.*`, `summary.*`, `ranker.*`, `preProcess`, `process`, `queue`, `upload`, `summaryClient`, `layoutWebhook`, `metrics`, `workspace.*` when enabled), read:
   - `replicas.desired` (and `replicas.max` if `cluster.hpa: true`).
   - `resources.requests.{cpu, memory}` and `resources.limits.{cpu, memory}`.
   - `node` (the target node group label).
3. Sum per node group: `Σ (replicas × resources.requests.{cpu, memory})` for the minimum footprint, `Σ (replicas.max × resources.limits.{cpu, memory})` for max burst at full HPA scale-out.
4. Add backing-service capacity (cache, db, file, search, stream — each chart-deployed via its own operator-managed Helm release, see `services-operators.md`).
5. Add storage (PVCs from chart-deployed backing services, plus the workspace cache PVC if enabled).
6. Pair the per-node-group footprint with the underlying compute pricing (cloud-provider instance pricing, on-prem hardware amortization, etc.).

The chart sets reasonable production-shaped defaults; tune them based on observed load.

> **AWS-only optional helper.** The upstream `groundx-on-prem` repo ships a Terraform-backed convenience tool at `bin/estimate` (with `bin/estimate.py`) that automates steps 1–3 for the AWS EKS deployment path — it renders the chart through `terraform/estimate/` and aggregates the result by node group. This is **optional AWS tooling** that builds on Terraform, not the canonical chart workflow. Deployers on Azure AKS, GKE, OpenShift, on-prem Kubernetes, or any non-AWS Kubernetes cluster do the same sums manually against the rendered values.

## 2. Where cost concentrates

Cost shows up in four buckets that materially differ in scale:

| Bucket | What drives it | Order of magnitude |
| --- | --- | --- |
| **GPU compute** | `layout-inference`, `ranker-inference`, `summary-inference` deployments. Each needs an NVIDIA GPU with specific memory minimums. | Highest. Single biggest line item on most deployments. |
| **CPU compute — orchestration + non-inference pipeline** | API tier, queue, pre-process, process, summary-client, the layout sub-microservices (correct, map, ocr, process, save), workspace runner, extract subsystem. | Medium. Scales with throughput and HPA settings. |
| **Backing services (cache, db, file, search, stream)** | Mode-dependent — chart-deployed in-cluster (operator-managed Helm releases) vs cloud-managed (RDS / S3 / OpenSearch Service / MSK / ElastiCache). | Highly variable. Cloud-managed is usually higher per unit but eliminates ops cost. |
| **Persistent storage** | OpenSearch index, MinIO bucket / S3, MySQL data, optional workspace PVC. | Grows with ingested document volume + retention. |

Network egress (between AZs, to/from cloud-managed services) is a fifth bucket; the chart doesn't drive it directly but trust-boundary-crossing engines (Google Cloud Vision OCR, external LLMs) generate measurable egress. See `ocr-mode.md` § 2 and `engines.md`.

## 3. GPU compute — the single biggest line item

The three inference deployments are the dominant cost driver on a vanilla deployment. Their chart defaults are documented at `cluster-requirements.md` § 2.2:

| Inference deployment | Default GPU memory per pod | Notes |
| --- | --- | --- |
| `summary-inference` | ~24 GB (Gemma 3 at default `1×1` workers/threads) | Disable via `summary.api.enabled: false` + `summary.inference.enabled: false` to drop this entirely and route to an external LLM (OpenAI / Azure / Bedrock). See `engines.md` and `service-substitution.md` § 4.6. |
| `ranker-inference` | ~24 GB (sized for `14×1` workers/threads) | Cannot reasonably be disabled — search ranking is core to RAG quality. CPU fallback is unreliable. |
| `layout-inference` | ~2.5 GB × `worker × thread` (default `1×6` ≈ 15 GB) | CPU fallback is possible via explicit override but degrades layout quality. |

The cost levers:

1. **Drop summary-inference entirely** by routing to an external LLM. This is the single biggest GPU-cost reduction available; the `eyelevel-gpu-summary` node group disappears.
2. **Right-size the layout GPU** by tuning `layout.inference.workers` and `layout.inference.threads`. Reducing from `1×6` to `1×3` cuts the GPU memory requirement to ~7.5 GB, opening up smaller (cheaper) cards like the L4 16 GB.
3. **Co-locate workloads via MIG / time-slicing** when GPU memory budget allows — single A100 80 GB can host `layout-inference` + `ranker-inference` + `summary-inference` simultaneously via MIG.

HPA on the inference deployments multiplies the GPU footprint by `replicas.max`. Each replica needs its own GPU (or MIG slice). Plan accordingly.

## 4. CPU compute — the orchestration + pipeline tier

For a vanilla deployment with all features enabled and HPA off, `cluster-requirements.md` § 6 documents the rough envelope: ~8-16 vCPU baseline for the orchestration tier, plus ~4-8 vCPU for the layout pipeline non-inference, plus ~1-2 vCPU each for `ranker-api` and `summary-api`. Total ~15-30 vCPU baseline at idle.

HPA multiplies this. With HPA on, `replicas.max` (often 16-32 for the high-throughput pods like `groundx`, `layout-api`, `process`) governs peak footprint. Compute the max-burst delta by reading `replicas.max × resources.limits` from rendered values; the difference between min and max-burst is the autoscaling headroom the cluster needs.

`workspace` adds ~5-10 vCPU baseline when enabled (6 deployments — see `workspace-service.md`). `extract` adds another ~2-5 vCPU baseline.

## 5. Backing services — chart-deployed vs cloud-managed

The substitution decision (see `service-substitution.md`) materially shifts cost.

### 5.1 Chart-deployed (operator-managed, in-cluster)

Each backing service runs in-cluster via its own Helm release (see `services-operators.md`). Cost is **node-group capacity** the deployer provisions:

| Backing service | Default footprint (rough, chart-deployed) | Node group target |
| --- | --- | --- |
| Cache (Redis StatefulSet) | ~0.2 vCPU / 0.5 GiB requests per pod, 1 replica default | `eyelevel-cpu-only` |
| Cache metrics | ~0.2 vCPU / 0.5 GiB per pod, 1 replica | `eyelevel-cpu-only` |
| MySQL (Percona) | ~0.6 vCPU / 0.5 GiB per pod + HAProxy ~0.6 vCPU / 1 GiB, `pxc.size: 1` default | `eyelevel-cpu-only` |
| Object store (MinIO) | ~0.1 vCPU / 0.25 GiB per pod, 1 server × 20 GiB default | `eyelevel-cpu-only` |
| Search (OpenSearch) | ~0.2 vCPU / 0.5 GiB per pod, 1 replica, single-node default | `eyelevel-cpu-only` |
| Stream (Kafka via Strimzi) | ~0.5-1 vCPU / 1-2 GiB per broker, 1 replica default | `eyelevel-cpu-only` |

Production scaling pushes each materially higher. `pxc.size: 3` (Percona quorum), `tenant.pools[0].servers: 4` (MinIO redundancy), OpenSearch with 3+ replicas, Strimzi with 3+ brokers — each adds ~3-5x the baseline footprint.

### 5.2 Cloud-managed

Backing-service cost shifts off the cluster's node budget onto cloud-provider line items:

| Backing service | Cloud-managed option | Cost driver |
| --- | --- | --- |
| Cache | AWS ElastiCache, GCP Memorystore | Instance size + cluster shards. |
| MySQL | AWS RDS, GCP CloudSQL, Azure Database for MySQL | Instance class + storage + read-replica count. |
| Object store | AWS S3, GCP Cloud Storage, Azure Blob | Storage GB + request count + egress. |
| Search | AWS OpenSearch Service, Aiven OpenSearch | Instance class + storage + replica count. |
| Stream | AWS MSK, Confluent Cloud | Broker instance class + storage + throughput tier. |

The cluster's node budget drops correspondingly. Whether total cost is lower depends on per-deployment specifics (cloud provider, instance class, scale).

### 5.3 Hybrid — most production deployments

Most production deployments end at **selective substitution**: stateful subsystems (db, file, stream, summary-inference) externalized to cloud-managed services for backup / DR / scaling; chart-deployed for lighter-state subsystems (cache, search if small). The chart-deployed half's footprint lives in the rendered values; the cloud-managed half is on the cloud-provider's pricing pages.

## 6. Persistent storage

For chart-deployed backing services, PVCs are provisioned against `cluster.pvClass`. Defaults (from the chart's seed values files under `src/groundx/values/{percona,minio,opensearch}/`):

| Service | Default PVC size | Notes |
| --- | --- | --- |
| MySQL (Percona) | `pxc.persistence.size: 20Gi` | Single-node default. Production scales to 100s of GiB. |
| MinIO tenant | `tenant.pools[0].size: 20Gi`, `volumesPerServer: 1` | Production scales to TiBs. |
| OpenSearch | `persistence.size: 20Gi` | Production scales with index size (function of ingested document count × dimension × replica factor). |
| Cache (Redis) | `persistence.capacity: 10Gi` (when `persistence.enabled: true` — default off) | Cache is normally ephemeral; persistence enabled only when the deployment uses Redis-backed durable state. |
| Workspace cache | `pvc.capacity: 20Gi` (chart-default, always rendered when `workspace.enabled: true`) | The chart always materializes a `{workspace.serviceName}-data` PVC for the secondary file API cache. Override `workspace.pvc.capacity` to size; the chart does not support an `emptyDir` mode. |

Storage costs scale linearly with the ingested document volume in the OpenSearch index and the MinIO bucket. A rule-of-thumb for the OpenSearch index: ~3-5x the source document size, depending on the chunking and embedding dimension.

## 7. Network egress

Outbound network from the cluster has cost implications for:

| Egress path | When it happens | Approximate cost |
| --- | --- | --- |
| Cross-AZ within a single cloud region | When the cluster spans multiple AZs (typical for HA deployments) | Per-GB charge between AZs. |
| To Google Cloud Vision | When `layout.ocr.type: google` is set | Per-API-call charge plus egress per image bytes. See `ocr-mode.md` § 2. |
| To external LLM endpoints | When `summary.existing.url` routes to OpenAI / Azure / Bedrock | Egress per request bytes + the LLM provider's per-token charge. |
| To cloud-managed backing services (cross-AZ) | RDS / OpenSearch Service / MSK / S3 in a different AZ than the cluster | Per-GB cross-AZ charge. |

For air-gapped deployments, all of these collapse to zero — no external egress is possible. For high-throughput deployments with external services, egress can become a meaningful line item (10-20% of total cost in some shapes).

## 8. Cost-modelling discipline

When estimating cost for a new deployment:

1. **Make the substitution decisions first** (see `service-substitution.md`). The chart-deployed vs cloud-managed split is the biggest single cost driver after GPU choice.
2. **Decide on the summary engine** (see `engines.md`). Self-hosted gemma vs external LLM materially changes the GPU footprint and the per-call LLM cost.
3. **Set HPA expectations.** Will the deployment run at low/medium/high throughput? Set `replicas.max` and `cluster.hpa` accordingly before estimating.
4. **Sum the rendered values.** Render `helm template` against your overrides, walk per-microservice replicas/resources, sum per node group. (AWS deployers may use `bin/estimate` to automate this; non-AWS deployers do it manually or via their own tooling.)
5. **Add cloud-managed line items** for any externalized backing services. Get per-service pricing from the cloud provider.
6. **Add storage** — sum the chart-deployed PVC defaults (or cloud-managed equivalent), plus the OpenSearch / MinIO scale factor over expected document volume.
7. **Add egress** — only meaningful if external engines or cross-AZ cloud-managed services are in play.
8. **Add ops cost** — chart-deployed backing services need ops attention (upgrades, backups, monitoring); cloud-managed offloads that. Reflect this in TCO, not just compute spend.

Don't skip step 1. Substitution choices propagate through every other estimate.

## 9. What this file does not cover

- **Per-microservice resource defaults** → `node-groups.md`.
- **Cluster-wide minimums and GPU model classes** → `cluster-requirements.md`.
- **Chart-deployed vs cloud-managed decision** → `service-substitution.md`.
- **Operator installation specifics** → `services-operators.md`.
- **Summary engine selection (the biggest single GPU lever)** → `engines.md`.
- **Workspace runner subsystem footprint** → `workspace-service.md`.
- **HPA / autoscaling specifics** → `autoscaling.md`.
- **AWS-specific helpers (e.g., `bin/environment` for VPC/EKS setup, `bin/estimate` for capacity aggregation)** → optional AWS tooling not required by the chart; out of scope here. The chart itself is cloud-agnostic.
- **Cloud-provider pricing math** → out of scope; consult cloud-provider pricing calculators. The chart only models the in-cluster footprint, not the per-instance / per-service pricing.
- **TCO modelling (license + support + ops + compute)** → out of scope; depends on procurement model.
- **Architectural cost rationale (why these GPUs at these sizes)** → `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.
