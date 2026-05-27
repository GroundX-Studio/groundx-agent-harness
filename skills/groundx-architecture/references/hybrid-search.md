# Hybrid Search

GroundX's search blends three things into one ranked response: **relevance** from a proprietary weighted query against rich per-chunk metadata in OpenSearch, **semantic similarity** from a fine-tuned re-ranker, and **a blended final score** that the `groundx` pod computes from both. This is materially different from pure-vector search — vector databases only do similarity matching; hybrid search adds relevance, weighted across the metadata that the agentic pipeline produced, and a finer-grained semantic signal from a purpose-built re-ranker.

In implementation, the search path is entirely in the **`groundx`** pod plus the **ranker pair** (`ranker-api` + `ranker-inference`). There is no separate "search service" pod.

## 1. Marketing altitude

GroundX search combines keyword + vector relevance with a fine-tuned re-ranker for semantic similarity, then blends both into one score. This is materially better than pure vector databases, which only do similarity matching — relevance over rich metadata catches what similarity alone misses.

## 2. Product altitude

A search request runs in two stages. **First**, a proprietary weighted query against the JSONL chunks indexed in OpenSearch pre-filters the candidate set — querying across the rich per-level metadata produced by the agentic pipeline (document summary and keywords, section summary and keywords, chunk keywords, the three chunk versions). **Second**, the fine-tuned re-ranker scores the candidates for semantic similarity. The final ranked result blends both scores. Search is exposed through the GroundX API at `POST /v1/search/{id}` (search a bucket or group) and `POST /v1/search/documents` (search a specific document set).

## 3. Conceptual / algorithmic altitude

The blended-scoring pattern is the architectural reason GroundX search outperforms pure-vector approaches. Two compounding effects.

**First, the pre-filter exploits the X-Ray's richness.** The agentic pipeline (per `agentic-pipeline.md`) produces a JSONL chunk for OpenSearch indexing that carries document-level summary and keywords, section summary and keywords, chunk keywords, and three chunk versions per chunk. OpenSearch's keyword and vector indices ingest those. The proprietary weighted query queries across these attributes with different weights — so a query matching strongly on section keywords contributes differently than one matching strongly on chunk text. A pure-vector approach would query against an embedding-only representation and miss most of this signal.

**Second, the final score blends semantic similarity and relevance.** The fine-tuned re-ranker produces a similarity score per candidate chunk against the query; the `groundx` pod aggregates that with the OpenSearch relevance score into a single blended value. A pure-vector approach scores on similarity alone and loses the relevance signal that the rich metadata + weighted query provides.

The pre-filter narrows the candidate set so the re-ranker isn't running against the entire chunk universe — approximately **100–200 candidate chunks** at the default scale. The exact number depends on the scope (a single bucket vs. grouped buckets) and is tunable per deployment. The architectural trade-off: a larger candidate set means more semantic scoring work and higher search latency, but a richer pool for the re-ranker to choose from.

## 4. System altitude

The entire search path runs in the **`groundx`** pod plus the **ranker pair**:

```
caller → groundx (API) → OpenSearch (proprietary weighted query → top N chunks)
                       → ranker-api → ranker-inference (similarity scores)
                       → groundx (aggregates final blended score)
                       → response
```

- `groundx` accepts the search request, runs the OpenSearch query directly (no separate search-service pod), calls `ranker-api` with the candidate set, aggregates the final score from the OpenSearch relevance and the re-ranker similarity scores, and returns the response.
- `ranker-api` (CPU) fronts `ranker-inference` (GPU). The re-ranker returns similarity scores per candidate; `groundx` does the score aggregation.
- The number of candidates re-ranked is approximately 100–200 at the default scale, varying with search scope (single bucket vs. grouped buckets) and deployment tuning.

For the full system topology see `overview.md` § 4.4 / § 4.5.

## 5. Implementation altitude

**Pods:**

| Pod | Runtime | CPU/GPU | Role |
| --- | --- | --- | --- |
| `groundx` | Golang | CPU | Search orchestrator: handles the API, runs the OpenSearch query, calls the ranker, aggregates the blended score |
| `ranker-api` | Python | CPU | Fronts the re-ranker; same interface shape `groundx` uses for any inference target |
| `ranker-inference` | Python | **GPU** (no reliable CPU fallback; the fine-tuned re-ranker depends on GPU for production throughput) | The fine-tuned re-ranker model; returns similarity scores per candidate |

**Stores:**

- **OpenSearch** holds the JSONL chunks (per `agentic-pipeline.md` § 8 + `store.md` § 5.3) and both keyword and vector indices derived from them. OpenSearch is the only retrieval store for the search path.
- The **X-Ray** lives in file storage and is served separately by `GET /v1/ingest/document/xray/{documentId}` — it is **not** what search queries against. Search reads the JSONL representation in OpenSearch.

**Search API:**

- `POST /v1/search/{id}` — search a bucket or group (the `id` resolves to the appropriate scope).
- `POST /v1/search/documents` — search a filtered document set.

See `groundx-api` for call patterns and request/response shapes.

**Pre-filter scaling:** the default top-N from the OpenSearch pre-filter lands at approximately 100–200 candidate chunks, varying with search scope (single bucket vs. grouped buckets) and deployment tuning. Deployers can tune this trade-off at the cost of search latency.

## 6. Security / compliance altitude

The search path is **entirely in-cluster** — no LLM provider involved. `groundx`, OpenSearch, and the ranker pair all stay inside the deployment's trust boundary, regardless of which LLM mode the agentic pipeline used during ingest. For the full identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

`ranker-inference` is metered as **inference-class** TPM in the `metrics` pod (per `overview.md` § 4.7). `groundx` API latency is the user-facing SLI for search — `groundx` is metered as API response time. OpenSearch query latency is the dominant factor in p99 search latency; `ranker-inference` GPU saturation is the dominant factor in p99 under high load. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

OpenSearch holds the **JSONL chunks** + the derived keyword and vector indices — this is what search queries against. The X-Ray lives in **file storage** (MinIO/S3); it's the customer-facing aggregate, not the search substrate. For storage placement of these and other artifacts see `store.md`.

## 9. Cost / FinOps altitude

`ranker-inference` is the **second-largest GPU cost driver** in default deployments (between `summary-inference` and `layout-inference`). Unlike `summary-inference`, the re-ranker is **not interchangeable with a 3rd-party service** — it produces a similarity score that hosted services don't generally expose in the form GroundX uses, and it's a fine-tuned model purpose-built for this scoring step. CPU fallback is not a reliable option either. **Cost is driven by GPU availability and also constrained by it** — GPU capacity sets the practical ceiling on how many `ranker-inference` pods can run. The pre-filter top-N is the other meaningful cost lever (smaller top-N = less GPU work per search). Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The agentic pipeline** that produces the JSONL chunks search reads: `agentic-pipeline.md`.
- **The X-Ray** as the customer-facing aggregate artifact: `agentic-pipeline.md` § 5 + `groundx-api/guides/05-document-understanding.md` § 5 for the canonical schema.
- **OpenSearch as a data store** (vs. specifically as a search index): `store.md`.
- **The exact field weights** of the proprietary weighted query and the score-blending formula: internal implementation detail; not architecturally meaningful at this skill's altitude.
- **GroundX search API call patterns** (request/response shapes, error handling): `groundx-api`.
- **End-to-end document journey from ingest to retrievable**: `data-flow.md`.
- **The underlying re-ranker model architecture name**: not used in external content; not named in this skill.
