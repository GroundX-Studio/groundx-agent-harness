# Core RAG Workflow

The fundamental GroundX usage pattern: ingest documents into a bucket, wait for
processing to complete, search the bucket, and pass the result directly to an LLM.
Every other guide in `guides/` extends or adapts this loop.

## 1. Overview

```
create or select bucket
        ↓
  ingest documents  →  returns processId
        ↓
poll until status = complete
        ↓
  search_content(bucketId, query)
        ↓
  pass result.search.text to LLM
```

All ingest operations are asynchronous. Do not attempt to search a bucket until
`document_getprocessingstatusbyid` returns `status: complete`. See §2 in
08-errors-and-limits.md for the full async ingest pattern.

> **Customizing the pipeline:** GroundX's default processing pipeline is designed for
> general-purpose RAG. Workflows let you modify what is extracted and how it is
> represented — for domain-specific RAG tuning, document classification, or structured
> extraction. See `guides/09-workflows.md` for the full workflow pipeline guide.

## 2. Step 1 — Select or create a bucket

A bucket is the searchable container. Every document belongs to exactly one bucket.
Before ingesting, you need a `bucketId`.

**MCP — create:**
```json
{ "name": "my-project" }
```
Tool: `bucket_create` → `bucket.bucketId`

**MCP — list existing:**
```json
{}
```
Tool: `bucket_list` → array of `{ bucketId, name, fileCount, ... }`

**REST — create:**
```http
POST /v1/bucket
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "name": "my-project" }
```

**REST — list:**
```http
GET /v1/bucket
X-API-Key: YOUR_API_KEY
```

If the bucket already exists, read `bucketId` from the `bucket_list` response. See
§1 and §2 in 04-buckets.md for full field details.

## 3. Step 2 — Ingest documents

Submit one or more documents to the bucket. The response returns a `processId` —
the documents are not yet searchable at this point.

**MCP — remote URL:**
```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/report.pdf",
      "fileName": "report.pdf",
      "fileType": "pdf"
    }
  ]
}
```
Tool: `document_ingestremote` → `ingest.processId`

**REST — remote URL:**
```http
POST /v1/ingest/documents/remote
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/report.pdf",
      "fileName": "report.pdf",
      "fileType": "pdf"
    }
  ]
}
```

For local files, the GroundX MCP server does not provide a direct tool. Upload the
file to GroundX-hosted storage via the pre-signed URL service, then submit the
returned hosted URL to `document_ingestremote`. See §5 in 02-ingest-patterns.md for
the three-step process. For website crawls, use `document_crawlwebsite`. See §1 and
§4 in 02-documents.md for full parameter tables and all supported `fileType` values.

## 4. Step 3 — Poll for completion

Poll until `status` reaches `complete` (or `error`). The status lifecycle is
`queued` → `training` → `processing` → `complete` (or `error`). Treat `training`,
`processing`, and `queued` as in-flight states; do not search until `complete`.

**MCP:**
```json
{ "processId": "the-process-id-from-step-2" }
```
Tool: `document_getprocessingstatusbyid`

**REST:**
```http
GET /v1/ingest/{processId}
X-API-Key: YOUR_API_KEY
```

**Response shape:**
```json
{
  "ingest": {
    "processId": "...",
    "status": "complete",
    "progress": {
      "complete": { "documents": [...], "total": 1 },
      "error":    { "documents": [], "total": 0 }
    }
  }
}
```

**Polling intervals:** every 5 seconds for single documents; every 30 seconds for
large batches or crawls. Stop when `status` is `complete`, `error`, or `cancelled`.
After `complete`, check `progress.error.documents` — a batch may partially succeed.

Do not proceed to search until `status` is `complete`. See §2 in
08-errors-and-limits.md for the complete polling strategy and callback alternative.

## 5. Step 4 — Search the bucket

Once documents are `complete`, submit a natural-language query against the bucket.

**MCP:**
```json
{
  "id": 1234,
  "query": "What are the key findings in the Q3 report?"
}
```
Tool: `search_content` → `search.text`, `search.results`

**REST:**
```http
POST /v1/search/1234
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "query": "What are the key findings in the Q3 report?"
}
```

The `id` parameter accepts a `bucketId`, `groupId`, or a bucket/group integer ID.
To search across multiple buckets, assign them to a group and search by `groupId`.
See §1 in 03-search.md for all search parameters including `n` (result count) and
`verbosity`.

## 6. Step 5 — Use the result

`result.search.text` is a pre-formatted string containing all retrieved chunks with
their metadata, ready to inject into an LLM prompt. Use it as the context block in
your system prompt.

```
system:
  {your instructions}
  ===
  {result.search.text}
  ===

user:
  {query}
```

`result.search.text` is the recommended consumption path. GroundX's internal LLM
has already rewritten and re-ranked the chunks — passing `search.text` directly
gives the downstream LLM GroundX's suggested context for answer generation.

If you need to build your own context from individual chunks, use
`search.results[n].suggestedText` (the LLM-optimized rewrite) rather than
`search.results[n].text` (the raw original). Each result also carries `score`,
`documentId`, `processId`, `bucketId`, `sourceUrl`, page images, bounding boxes, and
any metadata stored in `searchData`. This chunk metadata is also what source-aware UIs
usually use for citations and document/page previews.

See §3 in 03-search.md for the full response schema and pagination via `nextToken`.

## 7. Minimal end-to-end sequence

```
bucket_create         { name: "my-project" }
                      → bucketId: 1234

document_ingestremote { documents: [{ bucketId: 1234, sourceUrl: "...", fileName: "report.pdf", fileType: "pdf" }] }
                      → processId: "abc-123"

document_getprocessingstatusbyid  { processId: "abc-123" }
                      → status: "queued" … poll …

document_getprocessingstatusbyid  { processId: "abc-123" }
                      → status: "training" … poll …

document_getprocessingstatusbyid  { processId: "abc-123" }
                      → status: "complete"

search_content        { id: 1234, query: "key findings" }
                      → search.text: "..."

→ inject search.text into LLM system prompt alongside user query
```
