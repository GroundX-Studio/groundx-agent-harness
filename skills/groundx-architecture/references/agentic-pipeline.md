# Agentic Pipeline

The agentic pipeline is what turns a layout (typed elements with their constituent words, produced by the vision model + OCR fusion) into the **X-Ray** — a rich JSON document of summaries, keywords, and chunk versions that is the final product for a document. Agents run at three granularity levels (document, section, chunk) producing context that downstream hybrid search depends on. The pipeline output is written into two artifacts: the X-Ray itself in file storage (served by `document_getxray`) and **JSONL** chunks in OpenSearch (what hybrid search actually reads). The pipeline is implementation-led by the **summary triple** (`summary-client` + optional `summary-api` + `summary-inference`) and is the single largest GPU cost driver in default deployments.

## 1. Marketing altitude

Agents enrich each document at three granularity levels — the document as a whole, each section, and each chunk — producing rich metadata that preserves context during retrieval. This is what makes hybrid search accurate: the more context the search index carries, the more precise the retrieval against any query.

## 2. Product altitude

The pipeline produces the **X-Ray** for each ingested document — a structured JSON object with document-level summary and keywords, section-level summaries and keywords, chunk-level keywords, and three versions of each chunk (one tuned for LLM completions, one tuned for search, one preserving the original extracted text). For table and figure chunks, an additional meta-prompting step generates per-chunk processing instructions before the chunk agents do their work. The pipeline is conditional: `processLevel = full` runs the complete document/section/chunk pass; `processLevel = none` skips it entirely (raw ingest with no enrichment).

## 3. Conceptual / algorithmic altitude

The agentic pipeline is the **second half of the element-level reasoning story** that began in the vision model. Vision-model output gives the pipeline a typed layout — tables, paragraphs, and figures with their constituent words — and the pipeline runs narrow LLM-based agents over those small focused units at three granularity levels:

- **Document level** — agents produce the document summary and document keywords.
- **Section level** — agents produce per-section summaries and per-section keywords.
- **Chunk level** — agents produce chunk keywords and three chunk versions; for table and figure chunks, the LLM first generates **processing instructions** for the specific table or figure (a meta-prompting step that lets the chunk agents adapt to the element type).

This three-level structure is the *why* behind the cost-reduction story (per `vision-model.md` § 3): because each agent works on a small focused element rather than a whole page or document, smaller-context-window LLMs are sufficient for many steps — cheaper models per call, with more opportunity for parallel work across chunks. Keep the boundary precise: the top-level ingest pipeline still has sequential stages, and storage, OpenSearch, retained artifacts, and much of processing still scale with pages, elements, chunks, and retained metadata. The pipeline output (the X-Ray) carries everything downstream consumers need: the chunks that get indexed into hybrid search **plus** all the metadata known about the document and its chunks — `fileSummary`, `fileKeywords`, section summaries, per-chunk bounding boxes, page URLs (rendered page images), and per-chunk multimodal URLs (rendered images for tables and figures). The rich per-level metadata is what the proprietary weighted query and the fine-tuned re-ranker have to work with; the URLs are what source-view UIs and chat-with-citations widgets render.

The pipeline is **gated** by `processLevel`. When `processLevel = none`, no agentic enrichment runs and the document goes straight to terminal storage with no X-Ray. When `processLevel = full`, the complete document/section/chunk pass runs.

When extraction is enabled (per `extraction-architecture.md`), the **Extract microservice runs against the X-Ray** — not against the raw layout-map output. Sequencing: layout → agentic pipeline → X-Ray → extraction.

## 4. System altitude

The agentic pipeline runs through the **summary triple** of pods:

```
pre-process → (queue) → summary-client → (API-like) → summary-api → (Celery) → summary-inference
                                       └─ (API) → 3rd-party LLM (when summary.serviceType is set)
summary-client → (queue, callback) → pre-process
```

- **`pre-process`** orchestrates the document's pipeline. When `processLevel != none`, it enqueues to `summary-client`.
- **`summary-client`** is the API-client pod that orchestrates LLM calls. It speaks to either the **self-hosted** stack (`summary-api` + `summary-inference`) or a **3rd-party LLM** (OpenAI / Azure / DeepInfra / etc.) depending on `summary.serviceType`. The interface shape is identical in both cases.
- **`summary-api`** (when self-hosted) fronts `summary-inference` and looks like a 3rd-party API to `summary-client`. `summary-api → summary-inference` is Celery.
- **`summary-inference`** (GPU, when self-hosted) is the actual LLM.
- When the agentic pipeline completes, `summary-client` enqueues a callback to `pre-process`, which then proceeds to the next step (extraction if enabled, otherwise `process` for terminal storage).

For the full pipeline topology see `overview.md` § 4.5. For the engine taxonomy (six engine IDs) see `summary-service.md`.

## 5. Implementation altitude

| Pod | Runtime | CPU/GPU | Conditional | Role |
| --- | --- | --- | --- | --- |
| `summary-client` | Python | CPU | Always present when summary is enabled | API client; orchestrates LLM calls (self-hosted or 3rd-party); receives requests over queue from `pre-process`; sends callback over queue when done |
| `summary-api` | Python | CPU | Only when `summary.create=true` (self-hosted mode) | Fronts `summary-inference`; presents the same shape to `summary-client` as a 3rd-party LLM endpoint would |
| `summary-inference` | Python | **GPU** (no reliable CPU fallback; some LLM models support CPU but it's not architecturally counted on) | Only when `summary.create=true` | The self-hosted LLM |

**X-Ray output shape** (the JSON produced for each document; stored in file storage by `process` and served by `GET /v1/ingest/document/xray/{documentId}`). The architecture skill describes the *shape*; the canonical field-by-field schema is in `groundx-api/guides/05-document-understanding.md` § 5.

| Level | Contains |
| --- | --- |
| Document | `fileSummary`, `fileKeywords`, `fileType`, `language`, `sourceUrl` |
| Section (per chunk's `sectionSummary`) | Section summary (context shared across chunks in the same section) |
| Chunk | `chunk` ID, `contentType` (`paragraph` / `table` / `figure`), `pageNumbers`, `text` (raw OCR), `suggestedText` (LLM-optimized; same as `search.text`), `boundingBoxes`, `json` (structured content; shape varies by `contentType`), `narrative` (string descriptions aligned with `json[]`; tables and figures only), `multimodalUrl` (image URL for tables and figures) |
| Pages | `documentPages[]` — per-page `pageUrl` (rendered page image) and dimensions |

For table and figure chunks, an additional **chunk instruction** step runs first — the LLM generates per-chunk processing instructions that the downstream chunk agents consume. The resulting `json[]` structured content and `narrative[]` descriptions are what those instructions produce.

**Routing the LLM call:** `summary-client` selects between self-hosted and 3rd-party based on `summary.serviceType`. The system supports multiple engine IDs (covered in detail in `summary-service.md`). From the agentic pipeline's perspective, every engine looks like a 3rd-party API — `summary-client` is agnostic.

**Conditional behavior:** `processLevel` is binary — `full` runs the complete pipeline; `none` skips it entirely. The pipeline does not expose a partial-granularity mode (you don't enable section but skip chunk, for example).

## 6. Security / compliance altitude

`summary-client` runs in one of three modes, and the trust-boundary shape differs across them:

1. **3rd-party LLM** (`summary.serviceType` is `openai` / `openai-base64` / `azure` / `deep-infra`) — document content leaves the GroundX cluster on each LLM call.
2. **Bundled self-hosted** (`summary.create = true`) — content stays within the deployment's trust boundary. The bundled `summary-api` + `summary-inference` stack is the convenience option for customers who want self-hosted but don't already have their own LLM serving infrastructure.
3. **Customer-hosted LLM** — `summary-client` is repointed at the customer's existing self-hosted LLM endpoint; content stays within the customer's trust boundary. Used by on-prem customers who already operate their own LLM serving stack and prefer to reuse it.

The bundled self-hosted option exists for convenience, not solely because of trust-boundary concerns — though trust-boundary concerns are one reason customers select self-hosted over 3rd-party. For the full identity / trust model see `identity-and-trust.md`. For data-residency implications see `data-residency.md`.

## 7. Operations / SRE altitude

`summary-inference`, `summary-api`, and `summary-client` (in external-LLM mode) are all metered as **inference-class** in the `metrics` pod (per `overview.md` § 4.7) — tokens-per-minute drives their HPA. When self-hosted, `summary-inference` is a GPU pod that scales against the inference TPM signal; when external, the `summary-client` queue back-pressure metric is the autoscaling lever. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Input:** the fused layout-map output from the vision-model + OCR pipeline — typed elements (table / paragraph / figure) with their constituent words.

**Output:** the pipeline's deliverable becomes **two artifacts** at the terminal `process` step:

| Artifact | Where it lands | Consumed by |
| --- | --- | --- |
| **X-Ray** — the aggregated JSON document | File storage (MinIO/S3) | Customers (via `GET /v1/ingest/document/xray/{documentId}`); the Extract microservice when enabled |
| **JSONL** — chunks reformatted line-by-line for the search index | OpenSearch (vector + inverted indices) | Hybrid search (per `hybrid-search.md`) |

Both are derived from the same pipeline run. The X-Ray is the customer-facing artifact; the JSONL is what powers search. Intermediate artifacts (per-agent results, the chunk instructions for tables/figures, etc.) are written to file storage during processing. For the canonical data-residency framing see `data-residency.md`.

## 9. Cost / FinOps altitude

`summary-inference` is the **largest GPU cost driver** in default deployments. The element-level architecture is *why* smaller-context-window LLMs work for the agents — each agent operates on a small focused element rather than a whole page or document, so the LLM serving them doesn't need a frontier-context-window model. Stage-level parallelism can improve wall-clock throughput, but it is not a blanket claim that total cost, storage, or latency stops scaling with document size. Choosing a 3rd-party LLM service in place of the self-hosted summary stack shifts GPU cost to per-call API fees; that's the dominant cost-shape decision at this altitude. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The vision model + OCR pipeline** that produces the layout-map input: `vision-model.md`, and `layout-ocr.md`.
- **The summary-service pod-level details** (six engine IDs, per-engine routing, queue topology): `summary-service.md`.
- **The Extract microservice** that consumes the X-Ray: `extraction-architecture.md`.
- **Hybrid search and the re-ranker** that query the X-Ray + OpenSearch: `hybrid-search.md`.
- **The end-to-end document journey** through ingest, agentic pipeline, and terminal storage: `data-flow.md`.
- **OpenSearch as a store** of X-Rays and indexed chunks: `store.md`.
- **Customer retrieval of the X-Ray** via the GroundX API (`GET /v1/ingest/document/xray/{documentId}`): `groundx-api`.
