# Data Flow: End-to-End Document Journey + Search Round-Trip

This file walks through two flows: **ingest** (a document entering the pipeline and becoming retrievable) and **search** (a query returning ranked results). It synthesizes the pieces documented separately in `vision-model.md`, `agentic-pipeline.md`, and `hybrid-search.md`. For the visual topology see `overview.md` § 1.

## 1. Marketing altitude

A document goes in, is read by the fine-tuned vision model, enriched by agents at three granularity levels, and becomes retrievable through hybrid search. Searches return ranked results with rich context — page images, bounding boxes, source URLs — not just raw text.

## 2. Product altitude

**Ingest.** A document enters through the GroundX API, is split into elements by the vision model and OCR, enriched by the agentic pipeline at the document / section / chunk levels, and lands in two terminal artifacts: the **X-Ray** (a customer-facing aggregate JSON in file storage) and **JSONL chunks** (in OpenSearch, what hybrid search reads). Extraction runs as an optional branch when enabled per workflow.

**Search.** A query enters through the GroundX API, is matched by a proprietary weighted query against OpenSearch's keyword and vector indices, re-ranked by the fine-tuned re-ranker for semantic similarity, and returned as a blended-score ranked response.

## 3. Conceptual / algorithmic altitude

The pipeline is **single-direction with callbacks looping back to `pre-process`** between branches. `pre-process` is the central orchestrator from the moment ingest enters the queue layer — it dispatches to layout, summary, extraction (when enabled), and finally to `process`. Each branch runs to completion and returns to `pre-process` before the next branch starts; the branches don't fan out in parallel.

Two artifacts come out the back of ingest: the **X-Ray** (in file storage) is the customer-facing aggregate that downstream extraction also consumes; the **JSONL** chunks (in OpenSearch) are what hybrid search reads at query time. They are derived from the same agentic-pipeline output but live in different stores. Hybrid search never queries the X-Ray directly.

Search is much simpler than ingest. There are no callbacks; the search request is a single round-trip through `groundx` (which does the OpenSearch query directly) and `ranker-api` → `ranker-inference` (which provides the semantic similarity scores). `groundx` aggregates the blended final score and returns the response.

## 4. System altitude

For the full system topology see `overview.md` § 4.4 and the Mermaid diagram in § 1. The ingest flow traverses CPU services orchestrated through queue-based handoffs; calls into the layout pipeline, the summary triple, and (when enabled) the extract microservice happen through API boundaries; each sub-pipeline returns through a callback (either to `layoutWebhook` or directly to `pre-process`) that ends in a queue enqueue back to `pre-process`. The terminal `process` step writes two artifacts to different stores. Search runs entirely in `groundx` plus the ranker pair; OpenSearch is the single retrieval store.

## 5. Implementation altitude

### 5.1 Ingest flow

| Stage | What happens |
| --- | --- |
| **1. Entry** | Request hits `groundx` (the API Handler). Validation, routing. |
| **2. File handoff** | **Binary upload:** `groundx` handles the file itself and enqueues to `queue`. **URL-shared:** `groundx` enqueues to `upload` via queue → `upload` writes the file to file storage and the initial metadata record to the process-metadata DB → enqueues to `queue`. |
| **3. Pipeline entry** | `queue` enqueues to `pre-process` (via queue). |
| **4. Layout** | `pre-process` calls `layout-api` via API. The Celery-orchestrated layout pipeline runs: `layout-process` (per-document file manipulation: PDF→images, resolution normalization) → `layout-correct` (per-page rotation correction) → `layout-inference` (GPU, element detection) + `layout-ocr` (in parallel, word extraction) → `layout-map` (per-document fusion by spatial containment) → `layout-save`. `layout-save` calls back to `layoutWebhook` via API; `layoutWebhook` enqueues to `pre-process`. |
| **5. Summary** | **When `processLevel != none`:** `pre-process` enqueues to `summary-client` (via queue); the agentic pipeline runs at document / section / chunk levels through `summary-client` calling either the self-hosted `summary-api` + `summary-inference` (GPU) stack, a customer-hosted LLM endpoint, or a 3rd-party LLM. `summary-client` enqueues a callback to `pre-process` when done. **When `processLevel = none`:** stage skipped entirely. |
| **6. Extraction (optional)** | **When extraction is enabled** (`values.yaml` enables the Extract microservice **and** the workflow API request includes an extraction YAML): `pre-process` calls `extract-api` via API after summary completes. The extract sub-pipeline runs as Celery-orchestrated reconciliation + QA agents; final `extract-save` calls back to `layoutWebhook` via API; `layoutWebhook` enqueues to `pre-process`. **When extraction is disabled:** stage skipped entirely. See `extraction-architecture.md` for depth. |
| **7. Terminal write** | `pre-process` enqueues to `process` (via queue). |
| **8. Persist** | `process` writes the **X-Ray** (aggregated JSON document) to **file storage** (MinIO/S3), the **JSONL chunks** to **OpenSearch** (the index hybrid search reads), and final metadata to the **process-metadata DB** (MySQL/RDS + Redis). The pipeline is complete; the document is retrievable. |

### 5.2 Search round-trip

| Stage | What happens |
| --- | --- |
| **1. Entry** | Search request hits `groundx`. |
| **2. Pre-filter** | `groundx` runs the proprietary weighted query against OpenSearch — keyword + vector indices over the rich per-chunk metadata. OpenSearch returns the candidate set (approximately 100–200 chunks at default tuning). |
| **3. Re-rank** | `groundx` calls `ranker-api` (CPU) → `ranker-inference` (GPU) with the candidate set. The re-ranker returns a similarity score per candidate. |
| **4. Blend + respond** | `groundx` aggregates the final score from the OpenSearch relevance score and the re-ranker similarity score, orders the candidates, and returns the response. |

For depth on each search stage see `hybrid-search.md`.

## 6. Security / compliance altitude

The ingest flow crosses trust boundaries when `summary-client` is configured to call a 3rd-party LLM (per `agentic-pipeline.md` § 6). The bundled self-hosted summary stack and the customer-hosted LLM mode both keep document content within the deployment's trust boundary. Layout, OCR, the agentic pipeline (when self-hosted), the extract microservice, `process`, and the search path are all in-cluster — no external trust-boundary crossings. For the full identity / trust model and per-stage data-residency implications see `identity-and-trust.md` and `data-residency.md`.

## 7. Operations / SRE altitude

The pipeline is **stateless at every stage** — all state lives in the shared data stores. The hosted cloud service has a stuck-document monitor for restarting stuck ingest processes; on-prem deployments need their own equivalent of this restart-stuck-ingest pattern. The `metrics` pod meters queue back-pressure on every pipeline-orchestrating pod (`pre-process`, `process`, `queue`, `upload`, `summary-client` in external-LLM mode) and inference TPM on every GPU pod (`layout-inference`, `summary-inference`, `ranker-inference`). For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Inputs:** customer-provided documents (file content or URL).

**Intermediate artifacts** (written to file storage during processing):

- `upload` writes the source file.
- Layout pipeline writes per-page images, OCR text, detection results, mapped layouts.
- `summary-client` writes summary intermediate artifacts.

**Terminal outputs:**

- **X-Ray** to file storage (MinIO/S3) — customer-facing aggregate; served by `GET /v1/ingest/document/xray/{documentId}`.
- **JSONL** to OpenSearch — keyword and vector indices read these chunks for hybrid search.
- **Final metadata** to MySQL/RDS + Redis (process metadata DB).

**Search-time reads:** `groundx` reads the JSONL indices from OpenSearch + the process-metadata DB. The X-Ray is **not** read on the search path (see `hybrid-search.md` § 8); it's retrieved separately by API call when a customer needs the aggregated form. For the canonical data-residency framing see `data-residency.md`.

## 9. Cost / FinOps altitude

The pipeline's compute concentrates in **three GPU services**: `summary-inference` (largest cost driver), `ranker-inference` (second), and `layout-inference` (third). Everything else is CPU orchestration and I/O — comparatively cheap. Deployment-level cost framing and per-driver levers are owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The vision model** doing element detection: `vision-model.md`.
- **The agentic pipeline** producing the X-Ray and JSONL: `agentic-pipeline.md`.
- **Hybrid search and the re-ranker**: `hybrid-search.md`.
- **The Extract microservice's internal flow** (the per-category reconciliation + QA agents): `extraction-architecture.md`.
- **Per-microservice depth** (ingest-service, store, search-service, summary-service, layout-ocr, workspace-architecture): the M4 microservice files.
- **Pod-level specifics** (replica counts, autoscaling thresholds, GPU node selectors, deployment topology): `groundx-on-prem`.
- **The Mermaid system diagram**: `overview.md` § 1.
