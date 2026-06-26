# Store (Data-Store Tier)

The store tier is **where state lives**. Every pod in the GroundX architecture is stateless (per `overview.md` § 4.4 / § 4.5); the state they manipulate lives in three shared data stores selected per-deployment via `values.yaml`: **File Storage** (object store for source files, intermediate artifacts, and the terminal X-Ray), the **Process Metadata DB** (relational + cache for auth, status, queueing state), and the **Retrieval DB** (OpenSearch for the JSONL chunks and derived keyword + vector indices). This file documents these three as a tier; per-artifact placement and per-pod responsibilities are documented in the topic files that produce or consume each artifact.

## 1. Marketing altitude

Storage stays out of marketing content. See `data-flow.md` § 1.

## 2. Product altitude

GroundX stores three kinds of state:

- **File Storage** holds the source files customers upload, the intermediate artifacts produced during processing, and the **X-Ray** — the customer-facing aggregate JSON for each ingested document.
- **Process Metadata DB** holds the operational state customers see — auth records, document and workflow status, queueing state, customer / bucket / group records.
- **Retrieval DB** holds the **JSONL chunks** and derived keyword + vector indices that hybrid search reads at query time.

Each is deployment-selectable: managed cloud services (S3, RDS, ElastiCache) for cloud deployments; self-hosted equivalents (MinIO, MySQL, Redis) for on-prem deployments; OpenSearch in both cases.

## 3. Conceptual / algorithmic altitude

The store tier is the architectural counterpart of the stateless-pod tier. Two structural ideas drive the design:

**Statelessness pushes state down.** Every pod can scale horizontally (per `overview.md` § 4.4) because no state lives in pod memory or on pod-local disk — it all lives in the three stores. Recovery, HPA scaling, pod replacement, and concurrent processing all work cleanly because there is no shared pod-local state to coordinate.

**Each store is matched to its access pattern.** Object storage handles large blobs (files, page images, X-Rays) where read patterns are by-key and writes are append-only at the artifact level. The relational store handles small structured records with transactional integrity (status updates, auth, queueing) and Redis caches the hot subset. OpenSearch handles the per-chunk indices that hybrid search queries with keyword + vector + custom scoring — a workload neither object storage nor a relational DB serves well. This three-way split is what lets `pre-process` orchestrate many concurrent documents without contention: bulk artifacts hit file storage; small frequently-updated rows hit MySQL/Redis; query-time work hits OpenSearch.

The terminal-write step (`process` per `ingest-service.md`) is the only place that writes OpenSearch; everything else either writes file storage (many pods) or updates the process metadata DB (also many pods, progressively through the pipeline).

## 4. System altitude

The three stores and their backings:

| Store | Default on-prem backing | Default managed backing | Selector |
| --- | --- | --- | --- |
| **File Storage** | MinIO | S3 (or equivalent object store) | `values.yaml` |
| **Process Metadata DB** | MySQL + Redis | RDS + Redis / ElastiCache | `values.yaml` |
| **Retrieval DB** | OpenSearch | OpenSearch (managed or self-hosted) | `values.yaml` |

The backings are interchangeable at the abstraction layer — pod code talks to a configured backing through the same interface regardless of which target is selected. Other object-store and database backings can be wired through `values.yaml`; the above are the common defaults documented in `groundx-on-prem`.

For the full system topology see `overview.md` § 4.4. For the inter-pod store access patterns see `overview.md` § 2 (the communication matrix).

## 5. Implementation altitude

### 5.1 File Storage

| Aspect | Detail |
| --- | --- |
| Backings | MinIO (on-prem default) / S3 (cloud default); other object stores via `values.yaml` |
| Writers | `upload` (source file, URL-shared path); layout pipeline (per-page images, OCR text, detection results, mapped layouts); `pre-process` (orchestration intermediate artifacts); `summary-client` (summary intermediate artifacts); `process` (terminal X-Ray); `extract-save` (extraction results, when enabled) |
| Readers | `groundx` (serves X-Ray on `GET /v1/ingest/document/xray/{documentId}`); downstream pods reading intermediate artifacts produced earlier in the pipeline; Extract microservice reads the X-Ray when extraction is enabled |
| Notable artifacts | Source file (input); per-page rendered images; layout intermediate artifacts; **X-Ray** (terminal customer-facing aggregate JSON); extraction output (when enabled) |
| Presigned-URL utility | Cloud-service deployments have a `FileUpload` Lambda utility (per the private cloud-utilities reference); on-prem deployments need their own equivalent |

### 5.2 Process Metadata DB

| Aspect | Detail |
| --- | --- |
| Backings | MySQL (on-prem default) / RDS (cloud default); Redis for the cache layer (or ElastiCache in cloud) |
| Writers | `upload` (initial metadata record on URL-shared ingest); `queue` and `pre-process` (progressive status updates as the document moves through orchestration); `layoutWebhook` (status updates after layout / extract callbacks); `process` (terminal metadata write); `groundx` (auth / account / workflow CRUD) |
| Readers | `groundx` (auth, status queries, account/bucket/group lookups); `pre-process` (orchestration state); workspace runner pods |
| Notable contents in MySQL/RDS | Customer / bucket / group records; document / workflow status; auth state; queueing state |
| Notable contents in Redis | Process state; frequently-accessed API query results (read cache); metrics |
| Update pattern | **Progressive** — multiple pods update the metadata record as a document moves through the pipeline, not only at the terminal step |

### 5.3 Retrieval DB

| Aspect | Detail |
| --- | --- |
| Backing | OpenSearch (managed or self-hosted) |
| Writers | `process` — **the only pod that writes OpenSearch** (per `ingest-service.md` § 8) |
| Readers | `groundx` — the only pod that queries OpenSearch (on the search path; per `hybrid-search.md` § 4) |
| Notable contents | **JSONL chunks** (the per-chunk records produced by the agentic pipeline) + derived keyword + vector indices |
| Not stored here | The X-Ray (that lives in file storage); intermediate artifacts (file storage); auth / status / queueing state (process metadata DB) |

The single-writer / single-reader pattern for OpenSearch is the simplest contract in the architecture — every other store has multiple writers and/or readers.

## 6. Security / compliance altitude

All three stores are in-cluster (or in the deployment's cloud account) — there are no external trust-boundary crossings at the store tier itself. External crossings happen at the **`summary-client → 3rd-party LLM`** edge (per `agentic-pipeline.md` § 6), not at the store tier. Encryption-at-rest, key management, and customer-isolation invariants are documented in `identity-and-trust.md` and `data-residency.md`. The store tier is *where* the customer-isolation contract is enforced; this file does not define what that contract is.

## 7. Operations / SRE altitude

The `metrics` pod does not directly meter the stores — store-side metrics are typically read from the backing service's own monitoring surface (CloudWatch for managed AWS services, the OpenSearch monitoring API, Prometheus exporters for MinIO / MySQL / Redis in on-prem deployments). What the `metrics` pod *does* meter — and what indirectly reflects store health — is the queue back-pressure on every pipeline pod and the API response time on `groundx`: a store-tier slowdown shows up as ingest queue depth or search latency at those signals. For backup posture, RPO/RTO, and regional failover see `disaster-recovery.md`. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

The canonical artifact-to-store placement:

| Artifact | Store | Producer | Consumer |
| --- | --- | --- | --- |
| Source file | File Storage | `upload` (URL-shared) / `groundx` (binary upload path) | Layout pipeline; Extract microservice |
| Per-page rendered images | File Storage | Layout pipeline | Customers (via X-Ray URLs); UI source-view widgets |
| Layout intermediate artifacts (OCR text, detection results, mapped layouts) | File Storage | Layout pipeline | Agentic pipeline |
| Summary intermediate artifacts | File Storage | `summary-client` | `process` (for terminal write) |
| **X-Ray** (aggregated JSON) | File Storage | `process` | Customers (via `GET /v1/ingest/document/xray/{documentId}`); Extract microservice when enabled |
| **JSONL chunks** + keyword + vector indices | Retrieval DB (OpenSearch) | `process` | `groundx` (search path) |
| Auth / account / bucket / group / workflow records | Process Metadata DB | `groundx` | `groundx` |
| Document / workflow status, queueing state | Process Metadata DB | `upload`, `pre-process`, `process` (progressively) | `groundx`, `pre-process` |
| Extraction output (when enabled) | File Storage | `extract-save` | Customers via the GroundX API |

**Three single-store invariants worth restating:**

1. The **X-Ray** lives in File Storage — *not* OpenSearch.
2. The **JSONL chunks** (what hybrid search reads) live in OpenSearch — *not* in File Storage as the X-Ray.
3. **Only `process` writes OpenSearch.** Every other pod that interacts with state writes File Storage or the Process Metadata DB.

For per-artifact field-level shape see the topic file that produces that artifact: `agentic-pipeline.md` § 5 for the X-Ray; `groundx-api/guides/05-document-understanding.md` for the canonical X-Ray schema; `hybrid-search.md` § 8 for the JSONL chunk pattern.

## 9. Cost / FinOps altitude

The store tier sits behind the three GPU services (`summary-inference`, `ranker-inference`, `layout-inference` — per `data-flow.md` § 9) as a cost driver. Within the store tier:

- **OpenSearch capacity** scales with indexed chunk count, which scales with documents × pages × chunks-per-page. The keyword + vector indices grow roughly linearly with chunk count, and OpenSearch is provisioned per-node — both factors push it up the cost ranking at scale.
- **MySQL/RDS capacity** scales with document / workflow / customer record volume and the cache footprint Redis carries. At high document throughput this can be material.
- **File Storage** grows with the durable archive of source files + intermediate artifacts + X-Rays + extraction outputs. Object storage cost-per-GB is low; the lever is the artifact-retention policy.
- **Managed vs self-hosted** is a materially different cost profile across all three stores; the `values.yaml` selectors are the lever. Deployment-level cost framing across supported backings is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **What `process` writes at the terminal step** in full detail: `ingest-service.md` § 8 + `agentic-pipeline.md` § 8.
- **The X-Ray's field-level schema:** `agentic-pipeline.md` § 5 + `groundx-api/guides/05-document-understanding.md` § 5.
- **The JSONL chunk shape and the hybrid-search indices derived from it:** `hybrid-search.md` § 8.
- **The intermediate artifacts produced by the layout pipeline:** `vision-model.md`, `layout-ocr.md`.
- **Encryption-at-rest, key management, and customer-isolation enforcement at the store tier:** `identity-and-trust.md`, `multi-tenancy.md`.
- **Backup posture, RPO/RTO, regional failover:** `disaster-recovery.md`.
- **Data residency posture (GDPR / HIPAA / FedRAMP region selection):** `data-residency.md`.
- **Per-deployment store sizing and `values.yaml` selector specifics:** `groundx-on-prem`.
- **The presigned-URL upload utility in cloud-service deployments:** the private cloud-utilities reference.
