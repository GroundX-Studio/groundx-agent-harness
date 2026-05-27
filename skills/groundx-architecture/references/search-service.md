# Search Service

The search service is **not a separate pod** in GroundX. The search path runs entirely in the **`groundx`** pod (the API Handler) plus the **ranker pair** (`ranker-api` + `ranker-inference`). This file is the microservice-altitude view; the algorithm and end-to-end search behavior live in `hybrid-search.md`.

For most search questions open `hybrid-search.md` instead. This file captures the pod-level facts that don't fit there: which pods participate, how caching works, and what's *not* in the search path.

## 1. Marketing altitude

Not the canonical place — see `hybrid-search.md` § 1.

## 2. Product altitude

Not the canonical place — see `hybrid-search.md` § 2.

## 3. Conceptual / algorithmic altitude

Not the canonical place — see `hybrid-search.md` § 3.

## 4. System altitude

The search path is **three pods** + two stores:

```
caller → groundx → OpenSearch         (proprietary weighted query)
                 → ranker-api → ranker-inference   (similarity scoring)
                 → groundx (aggregates blended score) → response
```

`groundx` is the only pod that talks to OpenSearch on the search path. The ranker pair is the only other compute. No `search-api`, `search-worker`, or equivalent pod exists. For the full system topology see `overview.md` § 4.4.

## 5. Implementation altitude

| Pod | Runtime | CPU/GPU | Role |
| --- | --- | --- | --- |
| `groundx` | Golang | CPU | Accepts the search request, runs the proprietary weighted query against OpenSearch, calls the ranker, aggregates the blended final score, returns the response |
| `ranker-api` | Python | CPU | Fronts the re-ranker |
| `ranker-inference` | Python | **GPU** (no reliable CPU fallback) | The fine-tuned re-ranker model |

**Search-time cache.** `groundx` caches the search response in Redis for **~1 minute**, keyed on the exact query string + the resolved bucket ID. Repeated identical searches within the TTL skip the OpenSearch query and the ranker round-trip entirely. The cache TTL is short enough that newly-ingested documents become discoverable quickly; long enough that interactive UIs and dashboard refresh loops hit the cache.

**Auth.** Auth lookup on every API request — search included — follows the standard pattern: Redis if cached, MySQL/RDS if not. This is not search-specific; see `store.md` § 5.2 for the cache pattern and `identity-and-trust.md` for the auth model.

**Search API endpoints.** The search surface is `POST /v1/search/{id}` (bucket / group) and `POST /v1/search/documents` (filtered document set). For call patterns see `groundx-api`.

## 6. Security / compliance altitude

The search path is **entirely in-cluster** — no LLM provider involved (per `hybrid-search.md` § 6). For the trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

`groundx` is the API-response-time signal for search (per `overview.md` § 4.7); `ranker-inference` is metered as inference-class TPM. The 1-minute search cache materially affects ranker GPU load — sustained-bursty patterns from dashboards / UIs hit the cache; long-tail unique queries miss and drive ranker work. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

`groundx` reads JSONL chunks + keyword + vector indices from **OpenSearch** on the search path. The X-Ray is **not** read on the search path — it lives in file storage and is served separately (per `hybrid-search.md` § 8 + `store.md` § 8). For canonical artifact placement see `store.md`.

## 9. Cost / FinOps altitude

Not the canonical place — see `hybrid-search.md` § 9. The 1-minute cache is the one search-service-specific cost lever: a higher cache hit ratio directly reduces ranker GPU work.

## 10. What this topic does not cover

- **The hybrid-search algorithm** (weighted query, re-ranker, score blending): `hybrid-search.md`.
- **The fine-tuned re-ranker itself**: `hybrid-search.md` § 3 + § 5.
- **The end-to-end search round-trip in flow terms**: `data-flow.md` § 5.2.
- **OpenSearch as a store**: `store.md`.
- **Search API call patterns** (request/response shapes, error handling): `groundx-api`.
