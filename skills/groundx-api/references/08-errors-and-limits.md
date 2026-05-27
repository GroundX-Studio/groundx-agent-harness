# Errors and Limits

Cross-cutting reference covering HTTP error codes, the async ingest pattern, pagination,
and rate limits.

## 1. HTTP error codes

All GroundX API endpoints use standard HTTP status codes. The three codes that appear
consistently across the API are:

| Code | Meaning | Common causes |
|---|---|---|
| `200` | Success | Request processed successfully |
| `400` | Bad Request | Missing required field, invalid parameter type, invalid ID format, unsupported file type, invalid URL |
| `401` | Unauthorized | API key is missing, malformed, expired, or lacks permission to access the resource |

A `401` always means the `X-API-Key` header is wrong or the key does not have access to
the requested resource. Verify the key is present, correctly formatted, and belongs to an
account that owns the resource being accessed.

A `400` means the request body or path/query parameters failed server-side validation.
The response body typically includes a description of the problem. Common `400` causes:
invalid UUID format for IDs, unsupported `fileType` values, missing required fields
(`documents`, `bucketId`, `query`), or invalid `processLevel` values.

## 2. Async ingest pattern

Document ingest (`document_ingestremote`, `document_crawlwebsite`),
document updates (`document_update`), document copies (`documents_copy`), and bulk
document deletes (`documents_delete`) are all asynchronous. They return immediately with
a `processId` and a `status` of `queued`. The actual processing runs in the background.

**Do not assume a document is searchable until its status reaches `complete`.** The
status moves through `queued`, `training`, and `processing` while work is in progress,
then to `complete` or `error` when finished. `training` is typically the longest phase;
`processing` is brief and may be skipped on small documents. Always poll
`document_getprocessingstatusbyid` (§5 in 02-documents.md) after any ingest operation
before attempting to search the ingested content.

**Status lifecycle:**
```
queued → training → processing → complete
                               → error
                               → cancelled  (if cancelled via document_cancelprocess)
```

**Recommended polling strategy:**
- Poll every 5 seconds for short documents
- Poll every 30 seconds for large batches or website crawls
- Stop polling when status is `complete`, `error`, or `cancelled`
- Check `progress.error.documents` on `complete` — a batch may partially succeed

**Callback alternative:** All ingest operations accept `callbackUrl` and `callbackData`
to receive push notifications instead of polling. See §1.4 in 02-documents.md.

There is no platform-level timeout limit for document ingestion. Long-running ingest
jobs remain in an in-flight status until they complete, fail, or are cancelled. When a
document cannot be processed, its status is set to `error` and `statusMessage` carries a
human-readable explanation; if callbacks were configured, that status is pushed to the
callback URL. Protected, encrypted, or unreadable documents are not exposed as separate
first-class categories in the API contract.

## 3. Pagination with nextToken

The following operations return paginated results with a `nextToken` cursor:

| Operation | Paginated resource |
|---|---|
| `document_list` | All documents in the account |
| `document_lookup` | Documents by processId, bucketId, or groupId |
| `bucket_list` | All buckets in the account |
| `group_list` | All groups in the account |
| `search_content` | Search results |
| `search_documents` | Search results |

**How it works:**

1. Make the initial request with `n` to set the page size (default 20, max 100).
2. If more results exist, the response includes a `nextToken` string.
3. Pass `nextToken` in the next call to retrieve the next page.
4. Continue until **either** no `nextToken` is returned, **or** `len(results) < n`,
   **or** (for endpoints that return it) `remaining` is `null` / `0`. Use whichever
   signals are present in the response — `group_list` is known to return a non-null
   `nextToken` even on the last page, so callers should not rely on `nextToken` alone
   for that endpoint.

For `bucket_list` and `group_list`, the response additionally includes `total` (total
count) and `remaining` (how many are left after the current page) to help estimate
progress and to detect end-of-results reliably.

For document listing operations, `nextToken` is the only pagination mechanism — there is
no offset parameter.

## 4. Rate limits and good-citizen guidelines

Well-behaved applications stay below hard limits and apply self-imposed soft limits to
avoid hitting rate caps and degrading processing quality. The guidelines below are the
recommended operating targets for production UIs and agents.

### 4.1 Ingest limits

| Constraint | Recommended | Hard limit |
|---|---|---|
| File size | 25 MB | 25 MB (trial) / 50 MB (subscription) |
| Pages per document | 200 pages | 750 pages (PDF/PPTX/DOCX/HWP) |
| Documents per batch | 20 | 50 |

**Check file size and page count before uploading.** If a file exceeds either recommended
limit, split it before submitting. See §11 in 02-ingest-patterns.md for the full
pre-upload validation and splitting workflow.

The 200-page recommendation exists because very long documents produce large numbers of
chunks that dilute search relevance. Splitting at logical boundaries (chapters, sections)
and ingesting each part separately also makes it possible to surface the exact relevant
section rather than a distant chunk from a 400-page document.

Batch size of 20 (rather than the 50 hard limit) leaves headroom for retries and avoids
client-side or network timeout issues on slower connections. It is a good-citizen
recommendation, not a platform ingest timeout.

**Per-document-type limits:**

| Type | Hard limit |
|---|---|
| PDF / PPTX / DOCX / HWP | 750 pages per file |
| CSV / TSV / XLSX | 1,500 rows; 250K words (trial) / 500K words (subscription) |
| TXT | 250K words (trial) / 500K words (subscription) |
| JSON | 5 MB file size; 20 levels of nesting |
| Website crawl | 500 pages, depth 5 (trial); 2,000 pages, depth 8 (subscription) |

### 4.2 Search limits

| Constraint | Recommended |
|---|---|
| Concurrent searches | 3 |
| Searches per minute | 20 |

Queue or debounce search requests in the UI to stay within these targets. For
applications that fan out a single user query to multiple buckets or groups, count each
`search_content` call separately toward the concurrency limit.

### 4.3 Handling HTTP 429

If you receive a `429 Too Many Requests` response, back off and retry with exponential
delay — start at 1 second, double on each retry, cap at 60 seconds. Do not retry
immediately.

Use `health_list` or `health_get` (07-customer-and-keys.md §§6–7) to verify service
availability before submitting large ingestion workloads.
