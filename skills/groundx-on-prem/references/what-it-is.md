# What You're Deploying

This file documents **what GroundX is from a deployer's perspective** — the microservices that land on a Kubernetes cluster, what they connect to, what's opt-in, and what footprint they imply. It is *not* a restatement of architecture facts; for what each microservice *does*, route to `groundx-architecture`. Treat this file as a deployment-facing consumer of architecture facts, not as a second source of truth.

The architecture skill describes the system at 9 altitudes. This file picks one — the **deployer altitude** — and translates *what GroundX is* into *what's on your cluster*.

## 1. Microservice inventory

GroundX deploys as a Helm chart. The microservices that always land on the cluster:

| Capability group | Microservices | Runtime | Notes |
| --- | --- | --- | --- |
| **API + orchestration** (always on) | `groundx`, `upload`, `queue`, `pre-process`, `process`, `summary-client`, `metrics`, `layoutWebhook` | Golang | CPU-only orchestration tier. For pod-level role definitions see `groundx-architecture/references/ingest-service.md` § 5. |
| **Layout pipeline** (always on) | `layout-api`, `layout-process`, `layout-correct`, `layout-inference`, `layout-ocr`, `layout-map`, `layout-save` | Python | `layout-inference` is GPU-default (CPU possible — see § 4); the rest are CPU. For pod-level definitions see `groundx-architecture/references/layout-ocr.md` § 5. |
| **Ranker** (always on) | `ranker-api`, `ranker-inference` | Python | `ranker-inference` is GPU. For depth see `groundx-architecture/references/hybrid-search.md` § 5. |
| **Summary stack** (default-on) | `summary-api`, `summary-inference` | Python | Only deployed when `summary.api.enabled: true` + `summary.inference.enabled: true` (the **default**). `summary-inference` is GPU and **requires** a GPU — it does not run on CPU. When set to `false`, `summary-client` calls an external LLM instead, and these two microservices are not deployed. For depth see `groundx-architecture/references/summary-service.md`. |
| **Extract microservice** (opt-in) | `extract-api`, `extract-download`, `extract-agent`, `extract-save` | Python | Only deployed when `extract.enabled=true`. When disabled, these microservices **do not render at all** — there are no idle replicas. For depth see `groundx-architecture/references/extraction-architecture.md`. |
| **Workspace runner** (opt-in) | `workspace-api`, `workspace-workspace`, `workspace-provision`, `workspace-command`, `workspace-publish`, `workspace-cleanup` | Python | Only deployed when `workspace.enabled=true`. Requires `workspace.token` or `workspace.existingSecret` for git credentials. For depth see `groundx-architecture/references/workspace-architecture.md`. |

For the canonical microservice list, the upstream `groundx-on-prem` repo's `src/groundx/templates/_helpers/app/` directory is the source of truth (referenced from `groundx-architecture/references/overview.md` § 4.5 + § 6).

## 2. Surrounding services (backing dependencies)

GroundX needs five backing services. Each can be deployed in one of three modes selected through `values.yaml`:

| Backing | Mode 1 — existing customer-managed | Mode 2 — operator-managed dedicated | Mode 3 — cloud-managed |
| --- | --- | --- | --- |
| **File Storage** | Customer's existing object store (`file.existing.url`) | Operator-deployed MinIO (`file.enabled=true`) | S3 (`file.serviceType=s3` + `file.existing.url`) |
| **Process Metadata DB** | Existing MySQL (`db.existing.ro` / `rw` / `port`) | Operator-deployed Percona MySQL | AWS RDS (set `db.existing.*` to RDS endpoint) |
| **Cache** | Existing Redis (`cache.existing.addr`) | Operator-deployed Redis | AWS ElastiCache (set `cache.existing.addr` to ElastiCache endpoint) |
| **Retrieval DB** | Existing OpenSearch (`search.existing.url`) | Operator-deployed OpenSearch | AWS OpenSearch managed (set `search.existing.url` to managed endpoint) |
| **Queue** | Existing Kafka (`stream.existing.domain` / `port`) | Operator-deployed Kafka via Strimzi | AWS SQS (per-topic `stream.topics.<topic-name>.type: sqs`) |

For what each store *holds* (X-Ray, JSONL chunks, intermediate artifacts, process metadata, queueing state, audit log), route to `groundx-architecture/references/store.md`. For the customer-isolation enforcement model on these stores, route to `groundx-architecture/references/multi-tenancy.md`.

## 3. Node group targeting

GroundX targets five node-group label **values** via `nodeAffinity` + matching `tolerations` on every pod. The label values and their roles:

| Default label value | Role | Targets |
| --- | --- | --- |
| `eyelevel-cpu-only` | General CPU work | `metrics`, `layoutWebhook`, `groundx`, others on the orchestration tier |
| `eyelevel-cpu-memory` | CPU + higher RAM headroom | CPU microservices that need additional memory beyond the baseline (e.g., `pre-process` workers and certain layout sub-microservices); the deployer assigns by per-microservice `node:` field in values.yaml |
| `eyelevel-gpu-layout` | GPU for vision model | `layout-inference` |
| `eyelevel-gpu-ranker` | GPU for re-ranker | `ranker-inference` |
| `eyelevel-gpu-summary` | GPU for bundled summary stack | `summary-inference` (only when `summary.api.enabled: true` + `summary.inference.enabled: true`) |

The chart looks for these values under the node-label **key `eyelevel_node`** on the cluster's nodes (the bare key `node` should not be used — it conflicts with Prometheus / Grafana reserved metric labels). The five label values themselves are configurable via the `cluster.nodeLabels` block in values.yaml. For the override mechanics see `references/node-groups.md` § 1.1 and § 4.

## 4. GPU sizing facts

Each GPU microservice has a worker+thread model. Resource sizing is per worker+thread; replica counts sit on top.

### 4.1 `layout-inference`

- **~2.5 GB GPU memory per worker+thread.**
- **GPU is the default; CPU is possible** but the chart's default `resource.limits` and `resource.requests` request an `nvidia.com/gpu`. To run on CPU, the deployer must explicitly set `resource.limits` and `resource.requests` to CPU + memory values that *override* the GPU request. The fallback works (per `groundx-architecture/references/vision-model.md` § 5) but the deployer has to opt out of GPU deliberately.

### 4.2 `ranker-inference`

- **~1.25 GB GPU memory per worker+thread.**
- Worker+thread counts are sized for a **24 GB GPU**.
- **CPU is unreliable.** Probably works, very slow, not architecturally supported as a production option. Plan for GPU. (See `groundx-architecture/references/hybrid-search.md` § 5 for the no-reliable-CPU-fallback framing.)

### 4.3 `summary-inference` (only when `summary.api.enabled: true` + `summary.inference.enabled: true`)

- **GPU required.** Does not run on CPU. The model in use is **Gemma 3**.
- **24 GB GPU total**, **12 GB per worker+thread**.
- Disable this microservice by setting `summary.api.enabled: false` + `summary.inference.enabled: false` and pointing `summary-client` at an external LLM — see `groundx-architecture/references/summary-service.md` for the engine taxonomy and the trust-boundary implications.

GPU choice is the **single largest cost lever in the cluster** — running self-hosted summary alone is more GPU memory than the rest combined. For the cost-shape story see `groundx-architecture/references/data-flow.md` § 9; deployment-level cost framing is documented in `references/cost-estimation.md`.

## 5. Opt-in toggles

The deployer's main configuration choices, and what each one turns on or off:

| Toggle | What it controls | Default | Footprint impact |
| --- | --- | --- | --- |
| `summary.api.enabled` + `summary.inference.enabled` | Self-hosted vs external summary LLM | both `true` (self-hosted) by default | When `true`, `summary-api` + `summary-inference` deploy and require the `eyelevel-gpu-summary` node group. When both `false`, those microservices are not deployed and `summary-client` calls an external `/chat/completions` endpoint. |
| `extract.enabled` | Extraction microservice | `false` | When `true`, the extract microservices deploy. When `false`, they don't render at all. Per-document activation is further gated by the workflow API request carrying an extraction YAML — see `groundx-architecture/references/extraction-architecture.md`. |
| `workspace.enabled` | Workspace runner subsystem | `false` | When `true`, the workspace runner microservices deploy and a workspace token must be provided. When `false`, the runner is not present and GroundX Workspace facade endpoints return errors. |
| `metrics.enabled` + `cluster.hpa` | Autoscaling | both `false` by default; enable for HPA | When enabled, the `metrics` microservice publishes HPA signals (per `groundx-architecture/references/observability.md` § 5.1) and every other pod scales against them. When disabled, replicas are fixed at the configured count. |
| OCR backend | Tesseract vs Google Cloud Vision | Tesseract | Default is in-cluster Tesseract. Providing a `gcv.json` GCP service account file switches `layout-ocr` to GCV; document page images then leave the cluster on each OCR call. See `groundx-architecture/references/layout-ocr.md` § 5.2. |
| Image variants | Chainguard hardened distroless vs default | Default | Chainguard variant for FedRAMP / security-compliance deployments. See `references/image-variants.md`. |

## 6. External connections

What leaves the cluster at runtime — this is the deployer's network-policy / egress / data-residency surface:

| Connection | When | Notes |
| --- | --- | --- |
| Object store (S3 / MinIO / equivalent) | Always | Source files, intermediate artifacts, X-Rays. In-cluster (MinIO) or external (S3 / managed object store). |
| Relational DB (MySQL / RDS) | Always | Process metadata, auth, queueing state. In-cluster (Percona) or external (RDS). |
| Cache (Redis / ElastiCache) | Always | Hot process state, frequently-accessed API queries, metrics. In-cluster or external. |
| Search (OpenSearch) | Always | JSONL chunks + keyword + vector indices. In-cluster (operator) or external (AWS OpenSearch managed). |
| Queue (Kafka / SQS / equivalent) | Always | Inter-pod handoff. In-cluster (Strimzi) or external (SQS). |
| **3rd-party LLM** (OpenAI / Azure / DeepInfra / EyeLevel-hosted) | When `summary.api.enabled: false` + `summary.inference.enabled: false` and a 3rd-party `summary.existing.serviceType` is set | Document content leaves the cluster on each summary LLM call. Trust-boundary crossing. See `groundx-architecture/references/identity-and-trust.md` § 6.2 + `groundx-architecture/references/summary-service.md` § 6. |
| **Google Cloud Vision API** | When `gcv.json` is provided | Page images leave the cluster on each OCR call. Trust-boundary crossing. |
| **GitHub or GitLab** | When `workspace.enabled=true` and managed projects publish code | Git push to whatever remote is configured. See `groundx-architecture/references/workspace-architecture.md` § 5.3. |
| Model-weight downloads from S3 | At inference-pod startup or on version change | `layout-inference` and `ranker-inference` pull model blobs from S3 on init / when `config.py` target changes. See `groundx-architecture/references/ai-ml-lifecycle.md` § 5.1. |
| Container image registry | At pod start | Image pulls. Air-gapped deployments mirror images locally — see `references/air-gapped.md`. |

## 7. What a vanilla deployment looks like

With no overrides, a default deployment lands:

- The API + orchestration golang microservices.
- The layout pipeline (with GPU-default `layout-inference`).
- The ranker pair (with GPU `ranker-inference`).
- The summary stack (with GPU `summary-inference` and Gemma 3) — because `summary.api.enabled: true` + `summary.inference.enabled: true` is the default.
- All five surrounding services in operator-deployed-dedicated mode (MinIO, Percona MySQL, Redis, OpenSearch, Kafka via Strimzi).
- No extraction microservice (until `extract.enabled=true`).
- No workspace runner (until `workspace.enabled=true`).
- Tesseract OCR (until `gcv.json` is provided).
- HPA disabled (until `metrics.enabled` + `cluster.hpa` are both flipped).

> **Known gap.** A canonical "minimum-viable starter" `values.yaml` does not exist in the upstream repo today — that's a `references/values-yaml.md` + `examples/values.*.example.yaml` deliverable for later phases. Until it ships, the upstream `src/groundx/values.yaml` defaults are the practical starting point.

## 8. What this file does not cover

- **What each microservice *does*** (the architectural facts) → `groundx-architecture/references/ingest-service.md`, `vision-model.md`, `agentic-pipeline.md`, `hybrid-search.md`, `summary-service.md`, `layout-ocr.md`, `workspace-architecture.md`, `extraction-architecture.md`.
- **The pipeline shape** (groundx → upload → queue → pre-process → process; layout sub-pipeline; summary triple) → `groundx-architecture/references/data-flow.md`.
- **Trust boundaries, identity model, audit log** → `groundx-architecture/references/identity-and-trust.md`.
- **Customer isolation enforcement** at the store layer → `groundx-architecture/references/multi-tenancy.md`.
- **Per-store backing-service selection mechanics** (field-by-field `values.yaml`) → `references/services-prereqs.md` + `references/values-yaml.md`.
- **Per-node-group resource profiles** in depth → `references/cluster-requirements.md` + `references/node-groups.md`.
- **Install workflow** (ordered prereqs → services → application → verify) → `references/install-flow.md`.
- **GPU operator setup, NVIDIA Operator install, AKS runtimeClass** → `references/gpu-operator.md`.
- **Cost estimation** (`bin/estimate`) → `references/cost-estimation.md`.
- **Marketing or positioning** about why on-prem → `product-brand-gtm` (product altitude) or `master-brand-gtm` (master-brand altitude).
