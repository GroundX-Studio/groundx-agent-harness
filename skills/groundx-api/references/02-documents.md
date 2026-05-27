# Documents

This reference covers the 14 document MCP operations: ingesting files from remote URLs
or websites; polling and cancelling ingest processes; listing and querying documents;
updating document metadata; copying and deleting documents; and retrieving extract and
X-Ray data. Local-file uploads are handled by a pre-signed URL pattern that feeds into
`document_ingestremote` — the GroundX MCP server does not expose a dedicated
local-upload tool. See §3.

## 1. Ingest overview

All ingest operations are **asynchronous**. Submitting an ingest request returns a
`processId` immediately — processing happens in the background. Poll
`document_getprocessingstatusbyid` (§5) until `status` is `complete` or `error` before
treating documents as searchable.

### 1.1 Status lifecycle

```
queued → training → processing → complete
                               → error
                               → cancelled  (if document_cancelprocess is called)
```

`training` is the dominant in-flight state for typical documents — it covers the parser
and metadata-extraction phase. `processing` is brief and may be skipped entirely on
small documents. Treat `training`, `processing`, and `queued` all as "still in flight";
do not assume the document is searchable until `status` reaches `complete`.

### 1.2 processLevel

`document_ingestremote` accepts an optional `processLevel` field per document.
Website crawl (`document_crawlwebsite`) does **not** support `processLevel` — it is
absent from the `WebsiteSource` schema.

| Value | Behaviour |
|---|---|
| `full` | Text extraction/OCR + chunking + GroundX agentic reprocessing (default) |
| `none` | Text extraction/OCR + basic chunking only — no GroundX agentic reprocessing |

Use `full` for retrieval-augmented generation workloads. In `full`, GroundX performs the
agentic enrichment that makes chunks more useful for search and downstream LLMs:
semantic chunk shaping, document / section / chunk summaries, keywords, instructions,
and the other workflow-configurable reprocessing steps described in `06-workflows.md`.

Use `none` only when extracted text and basic chunks are sufficient and latency matters.
With `none`, files still go through OCR / text extraction so the source content can be
indexed, but they skip GroundX's agentic reprocessing. Do not use `none` for workflows
that depend on enriched chunks, X-Ray-style summaries, custom workflow steps, or
extraction output.

`processLevel` is not the switch that enables structured extraction. Structured
extraction is enabled by attaching an extract workflow to the account, bucket, group, or
document before ingest (§15 and `06-workflows.md`). `processLevel: full` provides the
agentic processing substrate that those workflows run on; it does not create extract
results by itself.

### 1.3 Supported file types

**Documents:** csv, docx, hwp, json, pdf, pptx, tsv, txt, xlsx

**Images:** bmp, gif (not animated), heif, ico, jpg, png, svg, tiff, webp

The values listed above are the **canonical** `file_type` values — they match the
SDK's `DocumentType` literal exactly. The server currently also accepts common spelling
variants (`heic`, `jpeg`, `tif`), but the SDK literal lists only the canonical names,
so passing the canonical form is the forward-compatible choice.

| Variant | Canonical (recommended) |
|---|---|
| `"heic"` (HEIC files) | `"heif"` |
| `"jpeg"` | `"jpg"` |
| `"tif"` | `"tiff"` |

### 1.4 Callbacks

Remote ingest, website crawl, and document update all accept two optional callback fields.

| Field | Description |
|---|---|
| `callbackUrl` | Endpoint that receives POST notifications as processing progresses |
| `callbackData` | Arbitrary string passed back unchanged in every notification |

Use callbacks in long-running workflows to avoid polling. Without a callback, poll §5.

### 1.5 searchData and filter

Both fields are optional key-value objects that travel with a document throughout its
lifetime.

- `searchData` — additional metadata fed into GroundX's ranking model at search time
- `filter` — key-value pairs used to pre-filter the candidate set before a search runs

`document_ingestremote` supports both fields. Website crawl (`document_crawlwebsite`)
supports `searchData` only — `filter` is absent from the `WebsiteSource` schema.

Both can be updated after ingest via `document_update` (§11).

GroundX does not automatically ingest or index EXIF metadata. If EXIF or other embedded
file metadata should affect filtering, ranking, or UI display, extract it before ingest
and pass the relevant fields explicitly as `filter` or `searchData`.

### 1.6 File name and generated keywords

`fileName` is human-readable document metadata and is returned on document records and
search results. It also participates in document keyword generation: the default
`doc-keys` step uses the file name as one of the contexts that influence generated
document keywords, which can affect search. Use meaningful file names when they carry
domain context; use `searchData` / `filter` for structured metadata that should be
explicitly available at search time.

### 1.7 sourceUrl, textUrl, xrayUrl — direct S3 URLs

The `sourceUrl`, `textUrl`, and `xrayUrl` fields returned by `document_get` (§10),
`document_lookup` (§9), and `document_getprocessingstatusbyid` (§5) are direct S3 URLs
that require no authentication. The unguessable UUID in the path is the access control
(a capability-URL pattern, similar to Dropbox shared links or S3 presigned URLs).

Treat the URLs as bearer tokens:

- Do not log them verbatim — anyone reading the log line can fetch the original document
  and the parsed X-Ray.
- Do not surface them to end-user clients unless you intentionally want the client to be
  able to read the underlying document; otherwise proxy them through your own
  authenticated endpoint.
- Assume each URL remains valid until the underlying document is deleted from the bucket
  (deletion propagates to S3 within seconds), and that your own logs / support tickets /
  LLM transcripts inherit that capability for the same lifetime.

## 2. document_ingestremote / POST /v1/ingest/documents/remote

Ingest one or more documents from publicly accessible URLs.

**MCP:**
```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/report.pdf",
      "fileName": "report.pdf",
      "fileType": "pdf",
      "processLevel": "full"
    }
  ]
}
```
Tool: `document_ingestremote` → returns `ingest.processId`, `ingest.status`

**REST:**
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

**Document object fields:**

| Field | Required | Description |
|---|---|---|
| `bucketId` | yes | Target bucket |
| `sourceUrl` | yes | Publicly accessible URL of the document |
| `fileName` | no | Display name; defaults to the URL filename |
| `fileType` | no | One of the supported types (§1.3); inferred from URL if omitted |
| `processLevel` | no | `full` or `none` (default `full`) — see §1.2 |
| `searchData` | no | Search-time metadata object — see §1.5 |
| `filter` | no | Pre-filter metadata object — see §1.5 |

The request body also accepts two optional top-level fields (outside the `documents` array)
that apply to the entire request: `callbackUrl` and `callbackData` — see §1.4.

**Response:**
```json
{
  "ingest": {
    "processId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "queued"
  }
}
```

Save `processId` and poll §5 until `status` is `complete`.

**Errors:** 400 — invalid document type or source URL; 401 — unauthorized for that bucket.

## 3. Local files — SDK ingest or pre-signed upload service

**The GroundX MCP server does not expose a tool for local-file upload.** A direct REST
endpoint, `POST /v1/ingest/documents/local`, accepts `multipart/form-data` (a `blob`
file part plus a `metadata` JSON part), but it is limited to 8 MB per file, one file
per call, and does not support callbacks. **Note:** the SDKs currently send
`application/json` to this endpoint and will not work as written; the multipart-only
requirement needs to be reflected in the OpenAPI / Fern config first before the SDKs
can call it.

For local files in application code, prefer the Python SDK `client.ingest()` or
`client.ingest_directory()` methods. They handle the pre-signed upload flow
automatically, then submit the hosted URL to `document_ingestremote` (§2). If you are
calling REST directly, use the same pre-signed URL pattern manually: upload to
GroundX-hosted storage via the pre-signed URL service, then submit the resulting hosted
URL to `document_ingestremote`. This avoids the 8 MB cap and the one-file-per-call
constraint, and gives the same 25–50 MB file size limit and 50-file batch capacity as
remote ingest. See §5 and §13 in 02-ingest-patterns.md for the manual and SDK flows.

### Pre-signed URL service

**Request:**
```http
GET https://api.eyelevel.ai/upload/file?name={fileName}&type={fileExtension}
```

`type` is the file extension without a leading dot (e.g. `pdf`, `docx`, `png`).

**Response:**
```json
{
  "URL": "https://s3.amazonaws.com/...",
  "Header": {
    "Content-Type": ["application/pdf"]
  },
  "Method": "PUT"
}
```

**Upload:**
```http
PUT {URL}
Content-Type: {Header["Content-Type"][0]}

<raw file bytes>
```

A `200` or `201` response indicates success.

**Hosted URL** — use as `sourceUrl` in the subsequent `document_ingestremote` call:
- The value of `GX-HOSTED-URL` in the pre-signed URL response headers, if present.
- Otherwise: the upload `URL` with its query parameters stripped.

**Python SDK shortcut.** `client.ingest()` handles these three steps automatically when
a local `file_path` is provided — it calls the pre-signed upload service, then submits
to `document_ingestremote` with the hosted URL:

```python
client.ingest(
    documents=[
        Document(
            bucket_id=1234,
            file_name="report.pdf",
            file_path="/local/path/report.pdf",
            file_type="pdf",
        )
    ]
)
```

## 4. document_crawlwebsite / POST /v1/ingest/documents/website

Crawl a publicly accessible website, following links recursively up to a configured depth
and page cap. Not supported for on-premises deployments. The `sourceUrl` must include the
protocol (`http://` or `https://`).

**MCP:**
```json
{
  "websites": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://docs.example.com",
      "depth": 3,
      "cap": 50
    }
  ]
}
```
Tool: `document_crawlwebsite`

**REST:**
```http
POST /v1/ingest/documents/website
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "websites": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://docs.example.com",
      "depth": 3,
      "cap": 50
    }
  ]
}
```

**Website object fields:**

| Field | Required | Description |
|---|---|---|
| `bucketId` | yes | Target bucket |
| `sourceUrl` | yes | Starting URL for the crawl; must include protocol |
| `depth` | no | Maximum link-follow depth from `sourceUrl` |
| `cap` | no | Maximum total pages to crawl |
| `searchData` | no | Metadata applied to every page ingested — see §1.5 |

The request body also accepts two optional top-level fields (outside the `websites` array)
that apply to the entire request: `callbackUrl` and `callbackData` — see §1.4.

**Response:** Same `ingest.processId` / `ingest.status` shape as §2.

**Errors:** 400 — invalid source URL; 401 — unauthorized for that bucket.

## 5. document_getprocessingstatusbyid / GET /v1/ingest/{processId}

Check the current status of an ingest process. Call this after any ingest operation until
`status` reaches `complete` or `error`. A reasonable polling interval is 5 seconds.

**MCP:**
```json
{ "processId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```
Tool: `document_getprocessingstatusbyid`

**REST:**
```http
GET /v1/ingest/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
X-API-Key: YOUR_API_KEY
```

**Response shape:**
```json
{
  "ingest": {
    "id": 0,
    "processId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "complete",
    "statusMessage": "",
    "progress": {
      "queued":     { "total": 0, "documents": [] },
      "processing": { "total": 0, "documents": [] },
      "complete":   { "total": 2, "documents": [...] },
      "errors":     { "total": 0, "documents": [] },
      "cancelled":  { "total": 0, "documents": [] }
    }
  }
}
```

`ingest.statusMessage` carries a human-readable message when `status` is `error`. If a
callback URL was supplied on ingest, the status update is also pushed to that callback
URL. GroundX does not explicitly classify protected, encrypted, or unreadable documents
into separate user-facing categories; they surface as document errors with an error
status message.

The five `progress` buckets are populated in JSON, but each bucket may be `None` on the
typed Python SDK response — even when `status == "complete"`, `progress.complete`
itself is `Optional[IngestStatusProgressComplete]` and can come back as `None`.
**Always guard before indexing**:

```python
status = client.documents.get_processing_status_by_id(process_id=PID)
ingest = status.ingest

if ingest.status != "complete":
    raise RuntimeError(f"ingest is {ingest.status}, not complete")

complete_bucket = ingest.progress.complete if ingest.progress else None
documents = complete_bucket.documents if complete_bucket else []
for doc in documents:
    print(doc.document_id, doc.file_name)
```

The same pattern applies to `progress.errors`, `progress.processing`, `progress.queued`,
and `progress.cancelled`.

**Errors:** 400 — invalid process ID; 401 — unauthorized to access that process.

## 6. document_cancelprocess / DELETE /v1/ingest/{processId}

Cancel a running ingest process. Documents that have already completed processing are
not removed; only queued or in-progress documents are cancelled.

**MCP:**
```json
{ "processId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```
Tool: `document_cancelprocess`

**REST:**
```http
DELETE /v1/ingest/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
X-API-Key: YOUR_API_KEY
```

**Response:** Same `ingest.processId` / `ingest.status` shape as §2; `status` will be
`cancelled`.

**Errors:** 400 — invalid process ID; 401 — unauthorized to access that process.

## 7. document_getprocesses / GET /v1/ingest

List recent ingest processes, sorted from most recent to least recent.

**MCP:**
```json
{ "n": 20, "status": "complete" }
```
Tool: `document_getprocesses`

**REST:**
```http
GET /v1/ingest?n=20&status=complete
X-API-Key: YOUR_API_KEY
```

**Query parameters:**

| Parameter | Description |
|---|---|
| `n` | Maximum processes to return; accepts 1–100, default 20 |
| `status` | Filter by status: `queued`, `training`, `processing`, `complete`, `error`, `cancelled`, `active`, `inactive` |

**Response:** `{ "processes": [...] }` — each process object (`IngestStatusLight`) has `id`
(integer), `processId` (uuid), `status`, and `statusMessage`.

## 8. document_list / GET /v1/ingest/documents

List all documents across all resources in the account.

**MCP:**
```json
{ "n": 20, "filter": "report", "status": "complete" }
```
Tool: `document_list`

**REST:**
```http
GET /v1/ingest/documents?n=20&filter=report&status=complete
X-API-Key: YOUR_API_KEY
```

**Query parameters:**

| Parameter | Description |
|---|---|
| `n` | Maximum documents to return; accepts 1–100, default 20 |
| `filter` | Return only documents whose name contains this string. **Not the same as the `filter` metadata object used at ingest time** — this is a simple substring match on `fileName`, not the access-control pre-filter. |
| `sort` | Attribute to sort by: `name` or `created` |
| `sortOrder` | `asc` or `desc` |
| `status` | Filter by processing status (`queued`, `training`, `processing`, `complete`, `error`, `cancelled`, `active`, `inactive`) |
| `nextToken` | Pagination token from a previous response |

**Response:** `{ "documents": [...], "nextToken": "..." }` — `nextToken` is omitted when
no further pages exist. Each document in `documents` is a full `DocumentDetail` object
(same fields as §10).

**Pagination:** When results are truncated, the response includes a `nextToken` value.
Pass it back in the next call to retrieve the next page.

## 9. document_lookup / GET /v1/ingest/documents/{id}

Look up documents associated with a specific `processId`, `bucketId`, or `groupId`. The
`id` parameter accepts any of these integer identifiers.

**MCP:**
```json
{ "id": 1234, "n": 20 }
```
Tool: `document_lookup`

**REST:**
```http
GET /v1/ingest/documents/1234?n=20
X-API-Key: YOUR_API_KEY
```

Accepts the same `n`, `filter`, `sort`, `sortOrder`, `status`, and `nextToken` query
parameters as `document_list` (§8). The `status` parameter accepts 8 values: `queued`,
`training`, `processing`, `complete`, `error`, `cancelled`, `active`, `inactive`. The
`filter` parameter is a substring match on `fileName` — not the ingest-time `filter`
metadata object used for access control (§1.5).

**Response:** `{ "documents": [...], "count": N, "remaining": N, "total": N, "nextToken": "..." }`
— `count` is documents in this page, `total` is across all pages, `remaining` is
documents not yet returned (null when none remain). Each document is a full `DocumentDetail` object (same fields as §10).

**Accumulating all documents (Python SDK):**

```python
docs = []
next_token = None

while True:
    kwargs = {"id": bucket_id, "n": 100}
    if next_token:
        kwargs["next_token"] = next_token

    response = client.documents.lookup(**kwargs)
    docs.extend(response.documents or [])

    next_token = response.next_token
    if not next_token or response.remaining == 0:
        break
```

Pass `n=100` to minimise round trips. Stop when `next_token` is absent or
`remaining` is `0`.

**Errors:** 400 — invalid process, bucket, or group ID; 401 — unauthorized to access that
resource.

## 10. document_get / GET /v1/ingest/document/{documentId}

Retrieve full metadata for a single document by its `documentId` (UUID).

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_get`

**REST:**
```http
GET /v1/ingest/document/9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "document": { ... } }` — full document object including `documentId`,
`fileName`, `fileType`, `fileSize`, `bucketId`, `processId`, `processLevel`, `status`,
`statusMessage`, `searchData`, `filter`, `sourceUrl`, `textUrl`, `xrayUrl`.

### 10.1 Two `processId`s — what each one tracks

The name `processId` (Python: `process_id`) appears twice in the API surface and the
two values are **not** equal. They identify different things:

| Where it lives | What it identifies | Used for |
|---|---|---|
| **Ingest-job process ID** — returned by `client.ingest()` as `ingest.process_id` | The ingest batch (one or more documents submitted together) | Polling with `client.documents.get_processing_status_by_id(process_id=...)` and cancelling with `client.documents.cancel_process` |
| **Document/lineage process ID** — stored on each document record (`document.process_id` here in §10) and copied to every search-result chunk (`chunk.process_id`, see `03-search.md` §1.2) | The document's lineage through the ingest pipeline | Tracing a chunk back to its parent document, and constructing OCR-map / X-Ray URLs that need both `processId` and `documentId` |

Don't compare them — `client.ingest(...).ingest.process_id` is **not** equal to
`client.documents.get(document_id=...).document.process_id`, even when they refer to
the same underlying ingest batch + document. Asserts of the form
`assert doc.document.process_id == ingest.ingest.process_id` will always fail.

In prose elsewhere in the harness, the document/chunk one is sometimes called the
*lineage process ID* to disambiguate.

**Errors:** 400 — invalid document ID; 401 — unauthorized to access that document.

## 11. document_update / PUT /v1/ingest/documents

Update mutable attributes of one or more existing documents. Updatable fields are
`fileName`, `filter`, and `searchData`. The update is asynchronous; it returns a
`processId` that can be polled via §5.

**MCP:**
```json
{
  "documents": [
    {
      "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49",
      "fileName": "q1-report.pdf",
      "searchData": { "department": "finance" }
    }
  ]
}
```
Tool: `document_update`

**REST:**
```http
PUT /v1/ingest/documents
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "documents": [
    {
      "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49",
      "fileName": "q1-report.pdf",
      "searchData": { "department": "finance" }
    }
  ]
}
```

**Document update object fields:**

| Wire/REST key | Python SDK attr (`DocumentUpdate`) | Required | Description |
|---|---|---|---|
| `documentId` | `document_id` | yes | UUID of the document to update. |
| `fileName` | `file_name` | no | New display name. |
| `filter` | `filter` | no | Replacement filter object (replaces existing, not merged). |
| `searchData` | `search_data` | no | Replacement searchData object (replaces existing, not merged). |

The request body also accepts two optional top-level fields (outside the `documents` array)
that apply to the entire request: `callbackUrl` and `callbackData` — see §1.4.

**Python SDK form** — pass `DocumentUpdate` instances, not plain dicts:

```python
from groundx import DocumentUpdate

client.documents.update(documents=[
    DocumentUpdate(
        document_id="9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49",
        file_name="q1-report.pdf",
        search_data={"department": "finance"},
    ),
])
```

See `references/12-python-sdk-objects.md` §2 for the full `DocumentUpdate` reference.

**Response:** Same `ingest.processId` / `ingest.status` shape as §2. Poll §5 to confirm completion.

**Errors:** 400 — invalid request type; 401 — unauthorized for that document.

## 12. documents_copy / POST /v1/ingest/copy

Copy documents from one bucket to another. Either copy specific documents by `documentIds`
or copy all documents from a source bucket with `fromBucket`. At least one of `documentIds`
or `fromBucket` must be provided.

**MCP:**
```json
{
  "toBucket": 5678,
  "documentIds": [
    "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49"
  ]
}
```
Tool: `documents_copy`

To copy all documents from a bucket:
```json
{
  "toBucket": 5678,
  "fromBucket": 1234
}
```

**REST:**
```http
POST /v1/ingest/copy
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "toBucket": 5678,
  "documentIds": ["9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49"]
}
```

**Request body fields:**

| Field | Required | Description |
|---|---|---|
| `toBucket` | yes | Destination bucket ID |
| `documentIds` | no | Array of document UUIDs to copy; omit to copy all documents from `fromBucket` |
| `fromBucket` | no | Source bucket ID; copies all its documents when `documentIds` is omitted |

**Response:** Same `ingest.processId` / `ingest.status` shape as §2. Poll §5 to confirm completion.

## 13. document_delete1 / DELETE /v1/ingest/document/{documentId}

Delete a single document by its `documentId`.

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_delete1`

**REST:**
```http
DELETE /v1/ingest/document/9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

**Response:** Same `ingest.processId` / `ingest.status` shape as §2.

**Errors:** 400 — invalid document ID; 401 — unauthorized to delete that document.

## 14. documents_delete / DELETE /v1/ingest/documents

Delete multiple documents in a single request. Deletion is queued asynchronously; the
response returns a `processId`.

**MCP:**
```json
{
  "documentIds": [
    "123e4567-e89b-12d3-a456-426614174000",
    "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49"
  ]
}
```
Tool: `documents_delete`

**REST:**
```http
DELETE /v1/ingest/documents?documentIds=123e4567-e89b-12d3-a456-426614174000,9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

Pass `documentIds` as a comma-separated query parameter.

**Response:** Same `ingest.processId` / `ingest.status` shape as §2.

**Errors:** 400 — invalid document ID; 401 — unauthorized to delete those documents.

## 15. document_getextract / GET /v1/ingest/document/extract/{documentId}

Retrieve extract results for a document.

**Requires** an extract workflow attached to the document, bucket, or group via
`workflow_add_to_id` or `workflow_add_to_account` *before* the document is ingested.
Without an attached workflow, this endpoint returns 404 (`We could not find extractions
for the documentId you provided`) for every document, regardless of `processLevel`.
`processLevel: full` produces the X-Ray (§16) but **does not** produce extractions on
its own.

The response is a freeform JSON object whose shape is determined by the workflow's
extract steps. See `06-workflows.md` for workflow authoring and the `groundx-extraction-workflows`
skill for schema-first extraction authoring.

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_getextract`

**REST:**
```http
GET /v1/ingest/document/extract/9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

**Errors:** 400 — invalid document ID; 401 — unauthorized to access that document; 404
— no extract workflow has produced output for this document.

## 16. document_getxray / GET /v1/ingest/document/xray/{documentId}

Retrieve X-Ray data for a document. X-Ray is a detailed structural analysis produced
during ingest. The response is a freeform JSON object. The document object returned by
`document_get` (§10) includes a `xrayUrl` field pointing to the full X-Ray payload.

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_getxray`

**REST:**
```http
GET /v1/ingest/document/xray/9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

**Errors:** 400 — invalid document ID; 401 — unauthorized to access that document.
