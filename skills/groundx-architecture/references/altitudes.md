# Altitudes: The Canonical 1-Paragraph Architecture Story At Each Altitude

This file is the single most-consulted reference in the skill. It carries the canonical one-paragraph version of *the whole GroundX architecture story* at each of the nine altitudes, so any agent grabbing a quick framing for that altitude pulls a vetted version.

The nine altitudes are: marketing, product, conceptual / algorithmic, system, implementation (named components), security / compliance, operations / SRE, data architecture, and cost / FinOps. Each section below holds one canonical paragraph.

---

## 1. Marketing altitude

GroundX is built to read enterprise documents the way a human does — visual layout first, then meaning — and to ground LLM answers in the source. Where general-purpose AI fails on visually complex, table-heavy, image-heavy documents at scale, GroundX is purpose-built for them, runs wherever the customer needs to run it (Helm chart with deployment-target examples for AWS-managed, Azure, **Red Hat OpenShift** (partnership), generic on-prem Kubernetes, minikube, and air-gapped environments), and has produced up to 99% accuracy on real customer workloads. Dozens of customer-built frontends are already in production on top of GroundX, built ad-hoc per-customer. The **Studio Harness** — the agent-facing development surface (skills, scaffolds, widgets) above the GroundX backend — is the aspirational default going forward for both customer and internal frontends; no frontends have been built with it yet. Common use cases include data extraction, grounded chat, and smart reports — each common enough that GroundX ships first-class implementation scaffolds — though the platform is not bounded to those.

## 2. Product altitude

GroundX combines a fine-tuned vision model (trained on 1M+ pages of enterprise documents — identifies tables, paragraphs, and figures), a three-level agentic pipeline that enriches content at the document, section, and chunk levels (and, when extraction is enabled, a dedicated extraction QA microservice), and hybrid search that blends keyword and vector retrieval with a fine-tuned re-ranker. These are the three components behind the accuracy claim. The Helm chart deploys to the customer's Kubernetes target of choice — AWS-managed, Azure, **Red Hat OpenShift** (partnership), generic on-prem, minikube, air-gapped, and others — with `values.yaml` selecting which backing services each component talks to. All pods are stateless and horizontally scalable. Customers reach the system through Fern-generated SDKs (`groundx-python`, `groundx-typescript`), direct REST APIs, three company-owned frontends (EyeLevel SSP, GroundX Dashboard, FraudX), or one of dozens of customer-built frontends (currently ad-hoc; the **Studio Harness** is the aspirational default for new frontends going forward).

## 3. Conceptual / algorithmic altitude

GroundX's accuracy is structurally different from page-level or document-level approaches because it operates at the **elemental level** of a document. Each page is normalized and rotation-corrected, then a fine-tuned vision model identifies the visual elements on the page (tables / paragraphs / figures — types plus bounding boxes), while an independent OCR pass extracts words plus their bounding boxes; the two outputs are then fused by spatial containment so each element becomes a typed object carrying its constituent words. The agentic enrichment pipeline then runs at three granularity levels — document, section, and chunk — *creating context around each element*. (Enrichment is gated by `processLevel`: when `processLevel = None`, the summary metadata generation pass is skipped entirely; otherwise the per-granularity-level agents run.) This produces three compounding benefits: **richer per-element metadata** that preserves context during RAG retrieval; **cognitive-load reduction** for the agents themselves (each agent works on a small focused element rather than a whole page or document, which is what makes per-element reasoning accurate at all); and **lower cost** — because each agent operates on a small element, it can use smaller-context-window models that cost materially less than the frontier-context-window models page-level or document-level approaches need. When the workflow includes an extraction YAML and the deployment enables the Extract microservice, a per-category agentic pass performs reconciliation and QA against the extracted fields — running *after* the summary pass completes. At query time, hybrid search blends OpenSearch keyword + vector scoring with a fine-tuned re-ranker that re-orders candidates against the query — the richer per-element metadata is what the re-ranker has to work with.

## 4. System altitude

GroundX runs as a set of **stateless** services connected by a queue layer (all state lives in the shared data-store tier; every component horizontally scalable). The canonical deployment is the **Helm chart on Kubernetes**, where every component is a pod. The **same core component graph also deploys as AWS Lambdas** in the GroundX-managed cloud service, with four additional cloud-only utility Lambdas for billing, monitor, health, and shared presigned-URL behavior. A **legacy Lambda pipeline** remains in maintenance to support WordPress plugins. Backing services are selected per deployment via `values.yaml`. Common backing-service pairings (the Helm chart ships `values.yaml` examples for AWS-managed, Azure, **Red Hat OpenShift** (partnership), generic on-prem, minikube, and air-gapped targets — the list is open-ended, not enumerative):

- **Queue:** Kafka, SQS, or another supported queue backend.
- **File storage:** MinIO, S3, or another supported object store.
- **Process metadata:** MySQL, RDS, or another supported relational DB.
- **Cache:** Redis (or a managed equivalent).
- **Retrieval database:** OpenSearch (self-hosted or managed).

Ingest traverses several CPU services orchestrated through the queue layer, calling GPU services (Document Layout, Metadata Generation) via API. Search calls a separate GPU service (Ranker) via API directly from the API entry point. The Extract microservice is **opt-in** — present only when `values.yaml` enables it, active per-document only when the workflows API request includes an extraction YAML.

External clients (`groundx-python` and `groundx-typescript` SDKs generated from `openapi.yml` via Fern, direct REST, the **Studio Harness**, three company-owned frontends with partner-tier API access — EyeLevel SSP, GroundX Dashboard, FraudX — and dozens of customer-built frontends, each one a single customer account to GroundX) all converge on the `groundx` pod, which is the single ingress for customer-tier, Workspace facade, and partner-tier APIs. Workspace operations route from `groundx` to `workspace-api`; Partner lifecycle operations route from `groundx` to the partner/customer resource handlers.

For deployment-specific selection logic, pod sizing, scaling, install workflow, and operator concerns, see `groundx-on-prem`.

## 5. Implementation altitude

**External API surface (above the cluster):** the `groundx-python` and `groundx-typescript` SDKs are Fern-generated from `openapi.yml` (the same spec also produces the public docs site). The Python SDK adds a hand-maintained `extract` submodule, high-level extraction workflow helpers, and convenience methods `ingest` / `ingest_directories` on top of the Fern baseline. The **Studio Harness** is the agent-facing development surface above GroundX (skills, scaffolds, widgets, workflow infra). No frontends — company or customer — have been built with the Harness yet; the Harness is the **aspirational** default for new frontends going forward (target: hours-to-days build time instead of the weeks-to-months ad-hoc builds have historically taken). All external surfaces hit `groundx` (the API Handler) as the single ingress. See `groundx-api` for SDK/REST semantics; Harness publishing and UI-building skills own the scaffolding and widget machinery.

**Three company-owned frontends — each architecturally distinct:**

| Frontend | API path | Websocket | Notes |
| --- | --- | --- | --- |
| **EyeLevel SSP** | GraphQL wrapper → `groundx` | `ws.eyelevel.ai` (partner-tier) | The oldest; predates current canonical patterns; materially divergent |
| **GroundX Dashboard** | `groundx-middleware` proxy → `groundx` | `ws.eyelevel.ai` (partner-tier) | Modern proxy pattern; conceptually similar to what Studio Harness scaffolds produce (Dashboard predates the Harness) |
| **FraudX** | API-based chat client → `groundx` | None — uses APIs directly | First shipping Outcome Plug-in; the modern recommended chat-client pattern (no `ws.eyelevel.ai` dependency) |

Each frontend has (or will have) its own dedicated topic file. They share the GroundX backend but their frontend architectures differ enough that grouping them into one file would lose detail.

**Customer-built frontends:** dozens in production, all ad-hoc per-customer builds. The Studio Harness scaffold (paired React/MUI frontend + TypeScript middleware proxy, analogous to `groundx-middleware`) is the **aspirational** default for new customer and internal frontends going forward; no production frontend has been built with it yet. Customer-tier API only; each customer is considered a single customer account to GroundX (key count and key management is the customer's call).

**Pods (all stateless, horizontally scalable):** GroundX is implemented as a set of named Kubernetes pods split between two runtimes: **golang** for orchestration / I/O services (`groundx`, `upload`, `queue`, `pre-process`, `process`, `summary-client`, `metrics`, `layoutWebhook`) and **python** for ML / inference / agentic services (the layout sub-pods, the summary self-hosted stack, the ranker pair, the extract sub-pods, the workspace runner sub-pods). The boundary is generally at the queue or API edges — golang services manage state and queue handoff; python services do the heavy compute. The canonical pod names (sourced from `groundx-on-prem/src/groundx/templates/_helpers/app/`):

**Core ingest CPU pipeline:**

- `groundx` — API Handler (HTTP entry; also performs the OpenSearch query on the search path).
- `upload` — File Uploader (writes file + initial metadata).
- `queue` — Start Process (queue topic: `file-update`).
- `pre-process` — Processor (queue topic: `file-pre-process`; calls `summary-client`).
- `process` — Save Results (queue topic: `file-process`; the only pod that writes OpenSearch).

**Layout pipeline:**

| Pod | Granularity | Role |
| --- | --- | --- |
| `layout-api` | — | Entry point (API from `pre-process`) |
| `layout-process` | Per-document | Initial file manipulation (PDF→images), resolution normalization; generates per-page processing requests |
| `layout-correct` | Per-page | Page rotation correction |
| `layout-inference` (GPU) | Per-page | The fine-tuned vision model — element-level reading; runs in parallel with `layout-ocr` |
| `layout-ocr` | Per-page | OCR (Tesseract default; Google Cloud Vision when `gcv.json` is provided); runs in parallel with `layout-inference` |
| `layout-map` | Per-document | Unions per-page results back into a single document-level layout |
| `layout-save` | Per-document | Final save; triggers API callback |
| `layoutWebhook` (golang) | — | API callback target; enqueues to `pre-process` |

(Progression order documented in `overview.md`.)

**Summary triple (Metadata Generation):**

- `summary-client` — CPU API-client pod that orchestrates LLM calls. Always present when summary is enabled.
- `summary-api` + `summary-inference` (GPU) — the self-hosted LLM stack, deployed only when `summary.create=true`. When `summary.serviceType` is `openai` / `openai-base64` / `azure`, `summary-client` calls the 3rd-party LLM directly and these two pods are not deployed.

**Ranker pair:**

- `ranker-api` (CPU) — fronts the re-ranker.
- `ranker-inference` (GPU) — the fine-tuned re-ranker model. Returns log probabilities; `groundx` aggregates the final score.

**Extract microservice (opt-in via `values.yaml` AND per-workflow extraction YAML):**

- `extract-api` — entry point for the microservice (called by `pre-process` via API after summary completes).
- `extract-download` — request queue (Redis-backed Celery).
- `extract-agent` — per-category reconciliation and QA agents; runs multiple times in the sequence.
- `extract-save` — writes extraction results to file storage; final `extract-save` calls back to `layoutWebhook` (NOT to `groundx` directly), which enqueues to `pre-process`.

Exact sequence is configurable via the extraction YAML — the invoice example runs `extract-api → extract-download → [parallel: reconcile-statement → qa-statement || reconcile-meters → qa-meters] → extract-save → reconcile-charges → extract-save → layoutWebhook`. The default (non-extraction) ingest path skips this microservice entirely; when enabled, extraction runs *after* summary metadata generation and before the terminal `process` write.

**Observability:**

- `metrics` — custom metrics for Horizontal Pod Autoscaling + Prometheus/Grafana dashboard reporting.

**Workspace runner subsystem (separate agent-facing API; not part of ingest):**

A 6-pod subsystem (`workspace-api`, `workspace-workspace`, `workspace-provision`, `workspace-command`, `workspace-publish`, `workspace-cleanup`) reached directly by workspace-capable agent surfaces through `workspace-api`. NOT orchestrated from `pre-process`. See `workspace-architecture.md`  for depth.

For per-pod responsibilities and inter-pod contracts in depth, see the topic file for that subsystem.

## 6. Security / compliance altitude

GroundX runs a narrow identity model — a single `X-API-Key` header carries customer-tier credentials; the partner tier uses an `X-API-Key` partner key plus an optional `X-Customer-Key` when operating on behalf of a managed customer; Basic Auth is reserved for the login / register / password-reset flow. There is **no customer API key rotation**, **no per-customer RBAC**, and **no SSO / OIDC / SAML** at the customer tier today; query-time scope-narrowing happens via the API's filter parameters. Customer isolation is enforced in two layers: a `groundx` API-layer ownership check on every request, plus a store-level customer-username validation on bucket access — both gating on the same owner identity. The deployment's trust boundary is closed by default; only two configurations cross it (3rd-party LLM when `summary.serviceType` is set; Google Cloud Vision when `gcv.json` is configured). A leaked partner key has full read/write blast radius across every customer the partner provisions. The `groundx` pod emits a comprehensive audit log of every API request — the only authoritative record — retained 1 year in the cloud service per SOC2; on-prem retention is the deployer's choice. Cloud-service compliance posture today is **SOC2 Type 1 + HIPAA** held; SOC2 Type 2 in progress. FedRAMP / IL6 / GDPR-explicit certifications are not held by the cloud service; on-prem is the path for deployer-attested certifications. For depth see `identity-and-trust.md`, `multi-tenancy.md`, `data-residency.md`.

## 7. Operations / SRE altitude

The `metrics` pod is the central observability surface: every pod reports its own metrics to Redis, the `metrics` pod aggregates and serves the Prometheus-compatible endpoint, and every other pod's HPA scales against that signal. The metric categories are **API response time** (`groundx`, `layout-api`, `layoutWebhook`, `extract-api`, `workspace-api`), **queue back-pressure** (`pre-process`, `process`, `queue`, `upload`, `summary-client` in external-LLM mode), **Celery task back-pressure** (all layout / extract / workspace sub-pods), **inference TPM** (`layout-inference`, `summary-inference`, `summary-api`), and a **system-overall estimated-TPM** signal every pod scales against. Logs land in CloudWatch in the cloud service and stdout on-prem; format is migrating from plain text to JSON structured (partial today). Distributed tracing uses OpenTelemetry (partial coverage today, migration in progress). Cloud alerts route to **Slack**. Customers see two operability surfaces: `GET /v1/health` (status of `search` and `ingest`, refreshed every 5 minutes by the `UpdateHealthStatus` Lambda probing a test search query + the `summary-client` service) and the per-customer quota meters on `GET /v1/customer`. **No public SLOs** are committed today; customer-contract specifics live in operational agreements. A cloud stuck-document monitor recovers some stalled ingest documents past the layout or extract cutoff; on-prem deployments need an equivalent. For depth see `observability.md`, `failure-modes.md`, `disaster-recovery.md`.

## 8. Data architecture altitude

State lives entirely in the three-store tier (every pod is stateless): **File Storage** (MinIO / S3) holds source files, intermediate artifacts produced through processing, and the X-Ray; **Process Metadata DB** (MySQL / RDS for durable structured records — customer / bucket / group / document / workflow / auth / queueing state — plus Redis for the hot subset: in-flight process state, frequently-accessed cached API queries, and metrics); **Retrieval DB** (OpenSearch) holds the JSONL chunks and derived keyword + vector indices that hybrid search reads. The agentic pipeline's terminal output becomes **two distinct artifacts** at the `process` step — the X-Ray written to file storage (the customer-facing aggregate JSON; retrieved via `GET /v1/ingest/document/xray/{documentId}` and the `xrayUrl` capability URL on `document_get`; consumed by the Extract microservice when extraction is enabled) and JSONL chunks written to OpenSearch (what hybrid search queries at retrieval). The Process Metadata DB is updated progressively through ingest by multiple pods (`upload`, `queue`, `pre-process`, `layoutWebhook`, `process`); **only `process` writes OpenSearch**. Customer data deletion (per document, per bucket, per customer) runs as an asynchronous background task (seconds-scale) and cascades across all three stores except for audit logs (1-year SOC2 retention in cloud) and Redis cache entries (natural TTL expiration). Encryption-at-rest is delegated to the backing services; no GroundX-managed KMS layer. For depth see `store.md`, `agentic-pipeline.md` § 8, `data-residency.md`, `multi-tenancy.md`.

## 9. Cost / FinOps altitude

GroundX does not currently expose reliable per-call or per-subsystem cost. Cost is expressed at the deployment level — cluster size, backing-service choice (which queue, object store, relational DB, and cache the customer chose via `values.yaml`), pod replica counts, and the GPU-vs-CPU split. GPU cost concentrates in three pods, ranked: **`summary-inference`** (largest), **`ranker-inference`**, **`layout-inference`**. The element-level architecture lets the per-element agents use smaller-context-window models, which is the structural reason GroundX is cost-competitive on accuracy-comparable workloads (see § 3). Choosing a 3rd-party LLM service in place of self-hosted summary shifts GPU cost to per-call API fees. The **stateless** pod design means replicas can scale to zero when there's no load, which is meaningful for managed deployments where unused replicas incur fixed cost. Deployment-level cost framing across supported deployment targets is owned by `groundx-on-prem`. Per-call cost numbers are not currently derivable from the architecture and should not be fabricated.

---

## Maintenance

When a paragraph above is updated, also re-verify it against the relevant topic file in `../references/` (e.g. an update to § 4 System should be reflected in `data-flow.md`, `ingest-service.md`, and `search-service.md` once those land). The altitude paragraphs are the canonical short framing; topic files carry the depth.

Add a `Last verified: YYYY-MM-DD` stamp per paragraph during quarterly re-verification.

| Paragraph | Last verified |
| --- | --- |
| § 1 Marketing | 2026-05-17 |
| § 2 Product | 2026-05-17 |
| § 3 Conceptual | 2026-05-17 |
| § 4 System | 2026-05-17 |
| § 5 Implementation | 2026-05-17 |
| § 6 Security / compliance | 2026-05-17 |
| § 7 Operations / SRE | 2026-05-17 |
| § 8 Data architecture | 2026-05-17 |
| § 9 Cost / FinOps | 2026-05-17 |
