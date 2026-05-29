# Search

How to search GroundX content, consume results in an LLM pipeline, and paginate
through large result sets. For pre-filtering search candidates using document
metadata, see `guides/07-filter-field.md`.

Before answering whether a search field exists, check
`00-api-surface-changelog.md`. As of SDK 3.5.4, search-result enrichment includes
inline `search.results[*].fileSummary` and `search.results[*].sectionSummary`.
Use `document_getxray` only when the user needs the richer full X-Ray payload.

## 1. Search operations

Two search tools are available:

| Tool | Use when |
|---|---|
| `search_content` | Searching a bucket or group by ID |
| `search_documents` | Searching a specific set of documents by `documentId` |

`search_content` is the standard operation for RAG. `search_documents` is for when
you have already identified the exact documents to search — for instance, after
a metadata lookup.

## 2. Basic search

**MCP:**
```json
{
  "id": 1234,
  "query": "What are the Q3 revenue figures?"
}
```
Tool: `search_content` → `search.text`, `search.results`

**REST:**
```http
POST /v1/search/1234
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "query": "What are the Q3 revenue figures?"
}
```

The `id` parameter accepts a `bucketId` or `groupId`. Searching a group searches
all buckets assigned to that group in a single call.

**Query length:** queries longer than 30 words are automatically rewritten by
GroundX's internal LLM into a keyword-focused form before semantic search runs.
The rewritten form is returned in `search.searchQuery` if rewriting occurred.
Short, natural-language questions work well and need no special formatting.

**For LLM completions, use `result.search.text` directly.** It is a pre-assembled,
prompt-ready string containing all retrieved context. Pass it as the context block
in your system prompt. See §3.2 for the full pattern.

## 3. Result shape

### 3.1 Top-level response fields

| Field | Description |
|---|---|
| `search.count` | Total number of chunks returned |
| `search.query` | The original query string from the request |
| `search.searchQuery` | The rewritten query if GroundX rewrote it; absent otherwise |
| `search.score` | Overall confidence score across all results |
| `search.text` | Pre-assembled LLM context string — see §3.2 |
| `search.results` | Array of individual chunk objects — see §3.3 |
| `search.nextToken` | Pagination cursor if more results exist — see §6 |

### 3.2 `search.text` — LLM context (recommended)

`search.text` is a pre-formatted string ready to inject directly into an LLM system
prompt. For every retrieved chunk GroundX weaves together the `suggestedText` rewrite,
the auto-generated `searchData` fields (document title, publisher, section summary,
document summary), and any user-supplied `searchData` metadata into a single coherent
context block. This is always the same regardless of `verbosity`. Use it directly:

```
system:
  {your instructions}
  ===
  {result.search.text}
  ===

user:
  {query}
```

**Token budget management** — `search.text` can become large when many results are
returned. If the combined text exceeds your model's context window, fall back to
iterating `search.results` and assembling context from `suggestedText` fields up
to your token budget:

```
if token_count(result.search.text) > budget:
    context = ""
    for chunk in result.search.results:
        if token_count(context + chunk.suggestedText) > budget:
            break
        context += chunk.suggestedText + "\n\n"
else:
    context = result.search.text
```

This preserves GroundX's relevance ordering while giving precise control over
how many tokens reach the model. Reduce `n` in the search request if you
consistently hit the budget before consuming all results.

### 3.3 `search.results` — per-chunk data

`search.results` is an array of individual chunk objects ordered by score descending.
Use it when building UIs that need source attribution, document page image rendering,
bounding box overlays, or any other per-chunk visualization. `verbosity` controls
whether this array is returned and whether `searchData` is included — see §4.1.

| Field | Type | Description |
|---|---|---|
| `score` | number | Combined relevance score (OpenSearch + semantic similarity) |
| `chunkId` | string | Unique system-generated identifier for the chunk |
| `documentId` | uuid | Unique system-generated identifier for the document |
| `processId` | uuid | ID of the ingest process that produced this document — use with `documentId` to construct the OCR map URL (see §10 in 08-source-view-ui.md) |
| `bucketId` | integer | Bucket the chunk belongs to |
| `fileName` | string | Name of the ingested source file |
| `fileSummary` | string | Document-level summary exposed inline on `search.results[*]` in current SDK/API surfaces; see `00-api-surface-changelog.md` |
| `sectionSummary` | string | Section-level context exposed inline on `search.results[*]` in current SDK/API surfaces; see `00-api-surface-changelog.md` |
| `sourceUrl` | uri | URL of the source document |
| `suggestedText` | string | LLM-agent rewrite of the chunk, optimized for LLM context. Semantically equivalent to `text` but not word-for-word — use this for context assembly. Not directly mappable back to individual words in the source document. |
| `text` | string | Raw chunk text as extracted from the source document by X-Ray OCR. Directly corresponds to the word-level atoms in the OCR map (§10 in 08-source-view-ui.md). |
| `searchData` | object | Auto-generated and user-supplied metadata — see §5 |
| `multimodalUrl` | uri | Image clipping of the table or figure the chunk represents (present when the chunk is a visual element such as a table or chart) |
| `boundingBoxes` | array | Coordinates of where the chunk appears on the source page(s) — see §3.4 |
| `pages` | array | Rendered page images with pixel dimensions — see §3.5 |

MCP `search_content` and REST search use the same result-field contract for the
same request, indexed result, and verbosity. If a live MCP response only returns
base fields, check whether the indexed data is missing those enrichments or the
deployment is stale; do not treat MCP as a reduced search surface.

When building context manually, use `suggestedText` rather than `text` — it is the
cleaned, contextualized rewrite GroundX produces.

For a complete guide to building chat UIs with page rendering and highlight overlays,
see `guides/08-source-view-ui.md`.

### 3.4 BoundingBoxDetail

Each entry in `boundingBoxes` describes a rectangle on a specific page of the source
document:

| Field | Type | Description |
|---|---|---|
| `pageNumber` | integer | 1-based page number where this bounding box appears |
| `topLeftX` | number | X coordinate of the upper-left corner |
| `topLeftY` | number | Y coordinate of the upper-left corner |
| `bottomRightX` | number | X coordinate of the lower-right corner |
| `bottomRightY` | number | Y coordinate of the lower-right corner |

Bounding boxes are the primary mechanism for rendering chunk highlight overlays on
document page images. Use `pageNumber` to select the matching entry from `pages`,
then map the four coordinates onto the page image to draw the highlight region.
A single chunk may span multiple pages and therefore have multiple bounding box
entries.

### 3.5 Pages

Each entry in `pages` describes a rendered page image for the page(s) the chunk
appears on:

| Field | Type | Description |
|---|---|---|
| `number` | number | 1-based page number |
| `imageUrl` | uri | URL of a JPG rendering of the page |
| `width` | number | Width of the page image in pixels |
| `height` | number | Height of the page image in pixels |

`width` and `height` are the actual pixel dimensions of the rendered image. Use them
to scale `boundingBoxes` coordinates correctly when drawing overlays — coordinates
are expressed relative to these dimensions.

## 4. Search parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `id` | yes | — | Bucket or group ID to search |
| `query` | yes | — | Natural-language question or keywords |
| `n` | no | 20 | Maximum number of results to return (max 100) |
| `verbosity` | no | 1 | Controls searchData inclusion — see §4.1 |
| `relevance` | no | 10.0 | Minimum relevance score threshold. Results below this score are excluded. |
| `filter` | no | — | MongoDB-style pre-filter expression — see `guides/07-filter-field.md` |
| `nextToken` | no | — | Pagination cursor from a prior response |

### 4.1 verbosity

`verbosity` controls whether the `search.results` array is returned and whether each
chunk includes its `searchData` field. It has **no effect on `search.text`**, which
always contains the full smart combination of chunk content and enrichment.

| Value | `search.results` array |
|---|---|
| `0` | Not returned |
| `1` (default) | Returned; `searchData` field omitted from each chunk |
| `2` | Returned; full `searchData` field included on each chunk |

Use `verbosity: 0` for the lightest response when only `search.text` is needed.
Use `verbosity: 2` when building a UI that displays source attributions, document
summaries, bounding boxes, or any per-chunk metadata alongside the LLM response.

## 5. searchData

`search.results[*].fileSummary` and `search.results[*].sectionSummary` are the
primary inline enrichment fields for current search-result handling. Use the
`searchData` field for custom metadata and older/full-verbosity metadata flows.

`searchData` is metadata attached to each chunk that enriches search results. It
has two sources:

**Auto-generated by GroundX** — during ingestion, GroundX's internal LLM analyzes
each document and generates:

| Field | Description |
|---|---|
| `documentSummary` | Summary of the full document the chunk is from |
| `sectionSummary` | Summary of the section the chunk appears in |
| `fullTitle` | Full title of the document or section |
| `publisher` | Publisher or source attribution extracted from the document |

These fields are normally generated for processed documents when the indexed data
has them, and they are what make `search.text` richer than a plain vector retrieval:
the rewritten chunk can arrive in the LLM context already annotated with its
document title, publisher, and section summary.

**User-supplied at ingest** — any key-value pairs you attach in the `searchData` field
when ingesting a document. These travel alongside the auto-generated fields and are
returned in `search.results[n].searchData` at `verbosity: 2`. Use this for metadata
you want displayed in your UI alongside search results, such as authors, tags,
internal document IDs, or category labels. See §7 in 02-ingest-patterns.md for how
to attach user-supplied searchData at ingest time.

**searchData vs filter:** `searchData` enriches and accompanies chunks — it is not
used for hard inclusion/exclusion. Use the `filter` field (§4, `guides/07-filter-field.md`)
when you need to control which documents are eligible to appear in results at all.

## 6. Pagination

If more results exist beyond the `n` returned, the response includes `search.nextToken`.
Pass it as `nextToken` in the next call to retrieve the next page:

**MCP — next page:**
```json
{
  "id": 1234,
  "query": "travel policy",
  "n": 20,
  "nextToken": "the-token-from-previous-response"
}
```
Tool: `search_content`

Continue until no `nextToken` is returned. See §3 in 08-errors-and-limits.md for the
general pagination pattern.
