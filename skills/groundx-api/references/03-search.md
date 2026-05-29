# Search

This reference covers the two search operations: `search_content` for searching a bucket,
group, or single document by ID, and `search_documents` for searching an explicit set of
documents by UUID.

Before answering whether a search field exists, check
`../guides/00-api-surface-changelog.md`. Current search-result enrichment includes
inline `search.results[*].fileSummary` and `search.results[*].sectionSummary`.
Use `document_getxray` or `xrayUrl` when the user needs the richer full X-Ray.

## 1. Search overview

### 1.1 Two search paths

| Operation | Scope |
|---|---|
| `search_content` | All documents in a bucket or group, or a single document by ID |
| `search_documents` | An explicit list of documents by UUID |

Use `search_content` for the common case — query everything in a bucket. Use
`search_documents` when you need to restrict the search to a precise subset of documents
identified by their UUIDs.

### 1.2 Response shape

Both operations return an identical `search` object:

| Field | Description |
|---|---|
| `search.text` | Pre-concatenated LLM-ready context string — pass this directly to a model |
| `search.query` | The original query as submitted |
| `search.searchQuery` | The actual query used, if GroundX rewrote it for better results |
| `search.count` | Total number of results returned |
| `search.score` | Overall confidence score across results |
| `search.results` | Array of individual chunk results (empty when `verbosity` is `0`) |
| `search.nextToken` | Pagination token if more results exist |

`search.text` is the suggested context GroundX creates for downstream LLM answer
generation. Use it when you want GroundX to assemble the prompt context for you.
`search.results` is returned so applications can inspect the individual chunks, build
their own context, or render source-aware UI. UIs commonly use the chunk metadata for
page images, document URLs, page numbers, bounding boxes, scores, and citation cards.

Each entry in `search.results` includes:

| Field | Description |
|---|---|
| `text` | Original source text from the document |
| `suggestedText` | LLM-agent rewrite of the chunk, optimized for LLM context |
| `score` | Relevance score for this chunk |
| `documentId` | UUID of the document the chunk came from |
| `processId` | UUID of the document's lineage through the ingest pipeline — use with `documentId` to construct the OCR map URL. **Not the same** as the ingest-job process ID returned by `client.ingest()`; see `02-documents.md` §10.1 for the disambiguation. |
| `fileName` | Display name of the source document |
| `fileSummary` | Inline document-level summary on `search.results[*]`; see `../guides/00-api-surface-changelog.md` |
| `sectionSummary` | Inline section-level context on `search.results[*]`; see `../guides/00-api-surface-changelog.md` |
| `sourceUrl` | Original URL of the source document |
| `chunkId` | Unique ID for this chunk |
| `bucketId` | ID of the content bucket the result belongs to |
| `boundingBoxes` | Page coordinates where this chunk appears |
| `pageImages` | Page image URLs for the pages containing this chunk |
| `pages` | Array of page objects (`imageUrl`, `number`, `width`, `height`) for pages containing this chunk |
| `multimodalUrl` | Image clipping if the chunk is a table or figure |
| `searchData` | Custom and system metadata (present only when `verbosity` is `2`) |

MCP `search_content` and REST search use the same result-field contract for the
same request, indexed result, and verbosity. If a deployed MCP response only has
the base fields after requesting rich results, treat that as missing indexed data
or a runtime compatibility issue to investigate, not as a different MCP schema.

### 1.3 Verbosity

The `verbosity` parameter (0–2) controls how much per-result data is returned:

| Value | Data returned |
|---|---|
| `0` | `search.text` only — no individual results |
| `1` | Results with all fields except `searchData` (default) |
| `2` | Full results including `searchData` per result |

Use `0` when feeding results straight into an LLM and per-chunk data is not needed.
Use `2` when you need custom metadata alongside results.

### 1.4 Relevance threshold

`relevance` sets the minimum score a chunk must reach to be included. The default is
`10.0`. Lower this value to broaden results; raise it to restrict to high-confidence
matches only.

### 1.5 Pagination

Both operations support cursor-based pagination. When `search.nextToken` is present in
the response, include it in the next call's `nextToken` field to retrieve the next page.

### 1.6 Pre-filtering

Both operations accept a `filter` object. If provided, only documents whose `filter`
metadata matches the given key-value pairs are included in the candidate set before
scoring. See §1.5 of the documents reference (02-documents.md) for how `filter` is set
during ingest.

### 1.7 Language strategy

For best RAG quality, keep one language per bucket. If documents are not in English,
configure the bucket for the supported language. For mixed-language corpora, either
split content into one bucket per language or use workflows to normalize the corpus and
query path to a single language. A common workflow pattern is: translate document content
to English during the ingest pipeline, then pre-translate user queries or customize the
`search-query` workflow stage to translate/rewrite queries into English before retrieval.

## 2. search_content / POST /v1/search/{id}

Search all documents within a bucket, group, or a single document. The `id` parameter
accepts a `bucketId` or `groupId` (integer) or a `documentId` (UUID string).

**MCP:**
```json
{
  "id": 1234,
  "query": "what are the termination conditions?",
  "n": 5,
  "verbosity": 1
}
```
Tool: `search_content`

**REST:**
```http
POST /v1/search/1234?n=5&verbosity=1
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "query": "what are the termination conditions?",
  "relevance": 10
}
```

For REST, `n`, `nextToken`, and `verbosity` are query parameters; `query`, `relevance`,
and `filter` are in the JSON body.

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `id` | yes | `bucketId`, `groupId` (integer), or `documentId` (UUID) |
| `query` | yes | Natural language search query |
| `n` | no | Max results to return; 1–100, default 20 |
| `relevance` | no | Minimum score threshold; default 10.0 |
| `verbosity` | no | Data verbosity level; 0–2, see §1.3 |
| `filter` | no | Pre-filter metadata object; see §1.6 |
| `nextToken` | no | Pagination cursor from a previous response |

**Response (abbreviated):**
```json
{
  "search": {
    "text": "Combined LLM-ready context from top results...",
    "count": 5,
    "query": "what are the termination conditions?",
    "results": [
      {
        "text": "Section 12.3: Either party may terminate...",
        "suggestedText": "Termination conditions (section 12.3): ...",
        "score": 87.4,
        "documentId": "DOCUMENT_UUID_1",
        "fileName": "contract.pdf"
      }
    ]
  }
}
```

**Errors:** 400 — invalid request data; 401 — unauthorized to access the resource.

## 3. search_documents / POST /v1/search/documents

Search a specific set of documents identified by their UUIDs. Use this when you know
exactly which documents to search and want to exclude all others.

**MCP:**
```json
{
  "documentIds": [
    "DOCUMENT_UUID_1",
    "DOCUMENT_UUID_2"
  ],
  "query": "payment schedule",
  "n": 10
}
```
Tool: `search_documents`

**REST:**
```http
POST /v1/search/documents?n=10
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "documentIds": [
    "DOCUMENT_UUID_1",
    "DOCUMENT_UUID_2"
  ],
  "query": "payment schedule",
  "relevance": 10
}
```

For REST, `n`, `nextToken`, and `verbosity` are query parameters; `documentIds`, `query`,
`relevance`, and `filter` are in the JSON body.

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `documentIds` | yes | Array of document UUIDs to search |
| `query` | yes | Natural language search query |
| `n` | no | Max results to return; 1–100, default 20 |
| `relevance` | no | Minimum score threshold; default 10.0 |
| `verbosity` | no | Data verbosity level; 0–2, see §1.3 |
| `filter` | no | Pre-filter metadata object; see §1.6 |
| `nextToken` | no | Pagination cursor from a previous response |

**Response:** Same `search` object shape as §2.

**Errors:** 400 — invalid request data; 401 — unauthorized to access the resource.
