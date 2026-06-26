# Ingest Service (CPU Orchestration Tier)

The ingest service is the **CPU orchestration tier** that drives a document from API entry to terminal storage. It is five **golang** pods — `groundx`, `upload`, `queue`, `pre-process`, `process` — connected by queue-based handoffs, with `pre-process` as the central orchestrator that dispatches to layout, summary, and (when enabled) extraction sub-pipelines before the terminal write. The GPU services these pods orchestrate are documented in `vision-model.md`, `agentic-pipeline.md`, and `extraction-architecture.md`. The end-to-end flow is documented in `data-flow.md`.

## 1. Marketing altitude

Topology stays out of marketing content. See `data-flow.md` § 1.

## 2. Product altitude

The ingest service is the orchestration tier customers don't see directly — it accepts a document, drives it through visual reading and agentic enrichment, and lands it in the search index. New documents become retrievable within minutes (typical) by way of this pipeline.

## 3. Conceptual / algorithmic altitude

The ingest service is built on three architectural choices:

1. **Queue-based handoff between stages.** Each major orchestration pod (`groundx`, `upload`, `queue`, `pre-process`, `process`) receives work from a Celery queue and enqueues to the next. The queue mechanism backs both Helm/K8s and cloud-Lambda deployment topologies (Kafka or SQS — selectable via `values.yaml`).

2. **`pre-process` as the central orchestrator.** Once a document enters the queue layer, `pre-process` drives the rest of the pipeline — it calls the layout sub-pipeline (API), the summary sub-pipeline (queue), the extract sub-pipeline (API, when enabled), and finally hands off to `process` for terminal storage. Each sub-pipeline returns through a callback (to `layoutWebhook` or directly to `pre-process` via queue) that ends in a queue enqueue back to `pre-process`. The branches run sequentially, not in parallel.

3. **Golang for orchestration; python for compute.** All five ingest-service pods are golang — chosen for the I/O-heavy, state-management role they play. The GPU services these pods orchestrate (`layout-inference`, `summary-inference`, `ranker-inference`) and the layout / extract sub-pipelines are python — chosen for the ML / inference / agentic work they do. The boundary sits at the queue and API edges between the two runtimes.

The pipeline is **stateless** (per the broader architecture's stateless property): every pod can scale horizontally because all state lives in the shared data-store tier.

## 4. System altitude

The ingest service traverses the queue layer in a fixed sequence:

```
groundx → upload (URL files only) → queue → pre-process → process
```

`pre-process` additionally dispatches to layout (every document), summary (when `processLevel != none`), and extract (when extraction is enabled) sub-pipelines; each returns via callback to `pre-process` before the next branch runs.

Two ingest entry paths converge at `queue`:

- **URL-shared files:** `groundx` enqueues to `upload` (via queue); `upload` writes the file to file storage and the initial metadata record to the process-metadata DB, then enqueues to `queue`.
- **Binary uploads:** `groundx` handles the file content directly (no `upload` step) and enqueues straight to `queue`.

For the full system topology see `overview.md` § 4.4. For the inter-pod communication matrix see `overview.md` § 2.

## 5. Implementation altitude

| Pod | Runtime | Role | Celery queue topic |
| --- | --- | --- | --- |
| `groundx` | Golang | API Handler — single ingress for customer-tier, Workspace facade, and partner-tier APIs; runs OpenSearch query on the search path; routes Workspace requests to `workspace-api` and Partner lifecycle/resource requests to their handlers | — (HTTP entry) |
| `upload` | Golang | File Uploader (URL-shared files only); writes file to file storage + initial metadata to process-metadata DB | `file-upload` |
| `queue` | Golang | Start Process — initial workflow handler; enqueues to `pre-process` | `file-update` |
| `pre-process` | Golang | Processor — central orchestrator; dispatches to layout (API), summary (queue), extract (API, when enabled); enqueues to `process` | `file-pre-process` |
| `process` | Golang | Save Results — terminal step; writes X-Ray to file storage, JSONL chunks to OpenSearch, final metadata to MySQL/RDS + Redis | `file-process` |

**Branches `pre-process` dispatches to** (depth in their own files):

| Branch | Mechanism | When | Reference |
| --- | --- | --- | --- |
| Layout | API call to `layout-api` | Always | `vision-model.md`, `layout-ocr.md`  |
| Summary | Queue enqueue to `summary-client` (topic `file-summary`) | When `processLevel != none` | `agentic-pipeline.md`, `summary-service.md`  |
| Extract | API call to `extract-api` | When extraction is enabled (per-deployment + per-workflow YAML) | `extraction-architecture.md`  |

**Stateless + horizontally scalable.** Every pod in the ingest service can scale to multiple replicas under HPA. State lives in the shared data-store tier — process-metadata (MySQL/RDS + Redis), file storage (MinIO/S3), retrieval DB (OpenSearch).

**Workspace runner is not part of ingest.** `pre-process` does not dispatch to `workspace-api`; the workspace runner is a separate agent-facing API reached through `groundx` (per `overview.md` § 4.5 and the workspace-runner topic file).

## 6. Security / compliance altitude

All ingest-service pods are in-cluster — no external trust-boundary crossings at this tier. External crossings happen downstream when `summary-client` is configured to call a 3rd-party LLM. The `groundx` pod handles authentication and authorization for customer-tier and partner-tier API requests; downstream pods receive already-authenticated work via the queue layer. For the full identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

Each ingest-service pod is metered through the `metrics` pod by **queue back-pressure threshold** — the autoscaling signal is depth on its consume queue. `groundx` is additionally metered as an **API response-time** threshold (it's the external ingress). Restart-stuck-ingest is handled in cloud-service deployments by the `MonitorPipeline` Lambda (per the private cloud-utilities reference); on-prem deployments need their own equivalent. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Inputs:** API requests at `groundx` — either binary file content or a URL to fetch.

**Intermediate writes during ingest:**

- `upload` writes source file to file storage + initial metadata record to process-metadata DB.
- `pre-process` writes orchestration-level intermediate artifacts to file storage.
- (The layout pipeline, agentic pipeline, and extract microservice — orchestrated by `pre-process` — write their own intermediate artifacts; depth in their respective files.)

**Terminal writes** (all done by `process`):

- **X-Ray** to file storage (MinIO/S3) — customer-facing aggregate; per `agentic-pipeline.md` § 8.
- **JSONL chunks** to OpenSearch — search index; per `hybrid-search.md` § 8.
- **Final metadata** to process-metadata DB (MySQL/RDS + Redis).

Process metadata is **progressively updated** through the pipeline by multiple pods, not only at the terminal step — `upload` writes the initial record, `pre-process` updates it through the orchestration, and `process` writes the final state. For storage-placement specifics see `store.md`.

## 9. Cost / FinOps altitude

The ingest-service pods are CPU-only golang services — comparatively cheap relative to the GPU services downstream. CPU cost is driven by replica count under HPA; queue back-pressure is the scaling signal, so cost rises with ingest throughput. Most of the pipeline's compute cost concentrates in the GPU services (`summary-inference`, `ranker-inference`, `layout-inference`) — the ingest service is the orchestration layer, not the compute layer. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The vision model + OCR sub-pipeline** that `pre-process` dispatches to: `vision-model.md`, `layout-ocr.md`.
- **The agentic enrichment** that runs after layout: `agentic-pipeline.md`, `summary-service.md`.
- **The Extract microservice** (optional branch after summary): `extraction-architecture.md`.
- **Hybrid search** (the read-side flow, not part of ingest): `hybrid-search.md`.
- **End-to-end document journey** with all branches woven in: `data-flow.md`.
- **System diagram** with the full topology: `overview.md` § 1.
- **Storage backing services** the ingest service writes to: `store.md`.
- **Workspace runner** (separate agent-facing API; not part of ingest): `workspace-architecture.md`.
