# Ingest Patterns

How to get documents into GroundX: which ingest method to use, what file types
and sizes are accepted, how to attach metadata, and how to handle large batches.

All ingest operations are asynchronous — they return a `processId` immediately and
process in the background. See §2 in 08-errors-and-limits.md for the full polling
pattern. See §1 in 01-core-rag-workflow.md for the end-to-end sequence.

## 1. Choosing an ingest method

The right method depends on which client is doing the ingesting.

### 1.1 From the Python SDK

Use only `client.ingest()` or `client.ingest_directory()` (full reference in §13).
Do not call lower-level methods such as `client.documents.ingest_remote()` from
Python code — they are not part of the supported Python SDK surface.
These are the preferred ingest paths for application code: they automatically handle
the pre-signed upload flow for local files and still land on the same remote / hosted
file limits described in §3.

| Method | Use when |
|---|---|
| `client.ingest()` | One or more documents, mix of local paths and URLs in the same call. The SDK detects which is which and routes local paths through the pre-signed upload service automatically. |
| `client.ingest_directory()` | Bulk-load every supported file in a directory tree. Blocks until all batches complete. Python only. |

For website crawls from Python, fall back to the raw REST or MCP path described
in §6 — the SDK does not currently expose `client.crawl_website()`.

### 1.2 From the TypeScript SDK

Use `client.ingest()` (§13) for files. For website crawls, use the underlying
operation directly.

### 1.3 Direct REST or MCP callers

| Operation | Use when |
|---|---|
| `document_ingestremote` | Files are accessible via URL — the standard path |
| Pre-signed upload → `document_ingestremote` | Files are on the local filesystem — see §5 |
| `document_crawlwebsite` | Ingest content from a website |

**The GroundX MCP server does not expose a tool for local-file upload.** The direct REST
endpoint `POST /v1/ingest/documents/local` accepts `multipart/form-data`, but it is
limited to 8 MB per file, one file per call, and no callbacks. For local files, use the
pre-signed upload service instead (§5): upload the file to GroundX-hosted storage, then
submit the returned URL to `document_ingestremote`. This gives the same 25–50 MB file
size limit and 50-file batch capacity as remote ingest. If you're calling from the
Python SDK, prefer §1.1 — the SDK handles the pre-signed upload and ingest call for you.

## 2. Supported file types

**Documents:**

```
pdf  docx  pptx  xlsx  csv  tsv  json  txt  hwp
```

**Images:**

```
bmp  gif (not animated)  heif  ico  jpg
png  svg  tiff  webp
```

Pass the type without the leading dot as the `fileType` field (e.g. `"pdf"`, `"docx"`).
The `fileName` field may use any name — it does not need to match the source file's
actual name. The values above are the **canonical** ones the SDK's `DocumentType`
literal lists; the server currently also accepts common spelling variants (`heic`,
`jpeg`, `tif`), but passing the canonical form is the forward-compatible choice. See
§1 in 02-documents.md for the canonical list and full `document_ingestremote` parameter
table.

## 3. File size and concurrency limits

| Constraint | Trial | Subscription |
|---|---|---|
| Remote / hosted file | 25 MB | 50 MB |
| Concurrent files per batch | 50 | 50 |

These limits apply to `document_ingestremote`. Files uploaded via the pre-signed URL
service (§5) are hosted by GroundX and ingested as remote documents, so they follow
the same limits — not the 8 MB constraint that the direct
`/v1/ingest/documents/local` REST endpoint imposes.

**Document-type specific limits:**

| Type | Limit |
|---|---|
| PDF / PPTX / DOCX / HWP | 750 pages max |
| CSV / TSV / XLSX | 1,500 rows max; 250K words (trial) / 500K words (subscription) |
| TXT | 250K words (trial) / 500K words (subscription) |
| JSON | 5 MB max; 20 nesting levels max |
| Website crawl | 500 pages, depth 5 (trial); 2,000 pages, depth 8 (subscription) |

There is no platform-level timeout limit for document ingestion. Ingest jobs are
asynchronous and may run for as long as the document and current queue depth require.
The soft limits in this guide still matter because smaller batches and logically split
documents reduce retries, client-side connection timeouts, and search-quality dilution.

## 3.1 Language handling for ingest and RAG

GroundX ingests documents natively in any language supported by the configured agentic
LLM and stores the processed content in that native language. In the GroundX cloud
service, the agentic LLM is currently Gemma 4 or OpenAI GPT-5.4, both of which have broad
language coverage. GroundX does not automatically translate all documents into English
by default during ingest.

For RAG search, keep one language per bucket for best results. If the bucket's language
is not English, update the bucket configuration to the supported language. For mixed
language corpora, use one of two patterns:

1. Use workflows to translate documents into English during the agentic pipeline, and
   either pre-translate user queries into English or customize the `search-query`
   workflow stage to translate/rewrite queries into English.
2. Create separate buckets per supported language and configure each bucket for that
   language.

## 4. Remote ingest

**MCP:**
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

Up to 50 documents may be submitted in a single call.

## 5. Local files: pre-signed upload service

For files on the local filesystem, the GroundX MCP server does not provide a direct
tool — upload the file to GroundX-hosted storage using the pre-signed URL service,
then submit the returned hosted URL to `document_ingestremote`. This is a three-step
process.

### Step 1 — Request a pre-signed upload URL

```http
GET https://api.eyelevel.ai/upload/file?name={fileName}&type={fileExtension}
```

`name` is the file's display name; `type` is the file extension without a leading dot
(e.g. `pdf`, `docx`, `png`). The response is JSON:

```json
{
  "URL": "https://s3.amazonaws.com/...",
  "Header": {
    "Content-Type": ["application/pdf"]
  },
  "Method": "PUT"
}
```

Extract `URL` (the upload destination), `Header` (required request headers — each value
is a list; use the first element), and `Method` (always `"PUT"`).

### Step 2 — Upload the file

PUT the raw file bytes to the returned `URL` with the `Header` values applied:

```http
PUT {URL}
Content-Type: application/pdf

<raw file bytes>
```

A `200` or `201` response indicates success.

### Step 3 — Determine the hosted URL

The `sourceUrl` to use in `document_ingestremote` is:

- The value of `GX-HOSTED-URL` in the pre-signed URL response headers, if present.
- Otherwise: the upload `URL` with its query parameters stripped (the clean S3 object URL).

Then submit to `document_ingestremote` exactly as you would any remote document, using
this hosted URL as `sourceUrl`:

```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "{hosted URL from step 3}",
      "fileName": "report.pdf",
      "fileType": "pdf"
    }
  ]
}
```

Tool: `document_ingestremote` → `ingest.processId`

**Python SDK shortcut.** The `client.ingest()` method in the GroundX Python SDK
handles all three steps automatically when a local file path is provided — it detects
whether the `file_path` field is a URL or a local path, calls the pre-signed upload
service for local paths, and routes everything through `document_ingestremote`. Use it
in preference to implementing the three steps manually.

## 6. Website crawl

**MCP:**
```json
{
  "bucketId": 1234,
  "sourceUrl": "https://docs.example.com",
  "cap": 50,
  "depth": 3
}
```
Tool: `document_crawlwebsite` → `ingest.processId`

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
      "cap": 50,
      "depth": 3
    }
  ]
}
```

`cap` limits the number of pages crawled. `depth` limits recursion depth from the
starting URL. The crawler ingests HTML content — it may not handle JavaScript-heavy
single-page applications well. See §3 in 02-documents.md for all crawl parameters.

## 7. Attaching metadata (filter and searchData)

Two optional metadata objects can be attached to each document at ingest time.
They serve different purposes and are queried differently at search time.

**`filter`** — key-value pairs applied as a pre-filter in OpenSearch before any
search query runs. When a search includes a `filter` expression, only documents
whose `filter` metadata matches are included in the OpenSearch candidate set. Use
this for access control, tenant isolation, or any hard inclusion/exclusion criterion.

**`searchData`** — metadata fed into GroundX's ranking model at search time and
returned in `search.results[n].searchData`. Use this for contextual metadata that
should accompany chunks in results (titles, authors, tags, categories) but is not
used for hard filtering.

```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/q3.pdf",
      "fileName": "q3-report.pdf",
      "fileType": "pdf",
      "filter": {
        "department": "finance",
        "security_level": 2,
        "roles": ["director", "executive"]
      },
      "searchData": {
        "quarter": "Q3-2025",
        "author": "Jane Smith"
      }
    }
  ]
}
```

Both fields accept the same value types: string, number, boolean, list of strings
or numbers, and nested objects. The total size of each field is limited to 40 KB per document. Both can be updated after ingest via `document_update` (§11 in 02-documents.md).

**`filter` is absent from `document_crawlwebsite`** — website crawls support
`searchData` only. See §1.5 in 02-documents.md for the full field reference.
See §4 in 07-filter-field.md for the filter query syntax at search time.

## 8. Batching large document sets

Keep batches to 20 documents or fewer — the API permits up to 50, but staying under
20 leaves headroom for retries and avoids timeout issues. For sets that exceed 20,
split into batches and wait for each batch to reach `complete` before submitting the
next:

```
document_ingestremote  { documents: [ ...20 docs... ] }
  → processId: "batch-1"

document_getprocessingstatusbyid  { processId: "batch-1" }
  → status: "complete"

document_ingestremote  { documents: [ ...next 20 docs... ] }
  → processId: "batch-2"
  ...
```

Poll every 30 seconds for large batches. After `complete`, inspect
`progress.error.documents` — a batch may partially succeed with some documents
erroring. See §2 in 08-errors-and-limits.md for recommended polling intervals and
the callback alternative.

## 9. Controlling the processing pipeline with workflows

Before controlling processing depth, it is worth knowing that the agentic processing
pipeline — how chunks are shaped, summarized, classified, transformed, or extracted
into structured fields — can be customized via **workflows**. A workflow assigned to a
bucket applies to every document ingested into it.

Workflows are a critical concept for any non-trivial GroundX integration. They enable
domain-specific RAG tuning, document classification, and structured extraction
pipelines. See `guides/09-workflows.md` for the full pipeline guide.

## 10. Controlling processing depth with `processLevel`

Each document in an ingest request accepts an optional `processLevel` field. It controls
whether GroundX stops after text extraction / OCR and basic chunking, or continues into
GroundX's agentic reprocessing pipeline:

| Value | Behaviour |
|---|---|
| `full` | Default. Runs OCR / text extraction, chunking, and GroundX agentic reprocessing: semantic chunk shaping, summaries, keywords, instructions, and workflow-configurable enrichment. Use this for RAG, X-Ray/document understanding, custom workflow steps, and any workflow that should emit extract results. |
| `none` | Runs OCR / text extraction and basic chunking only. Skips GroundX agentic reprocessing. Lower latency, lower cost, and only suitable when raw extracted text chunks are enough. |

Set it per document inside the `documents` array:

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

Omitting `processLevel` is equivalent to `"full"`. Use `"none"` only when you are
certain the application does not need enriched chunks, document / section / chunk
summaries, workflow steps, or extraction output — the agentic processing cannot be
retroactively applied without re-ingesting the document.

Structured extraction is controlled by workflows, not by `processLevel` alone. To
populate `document_getextract`, attach an extract workflow to the account, bucket,
group, or document before ingest. `processLevel: full` gives that workflow the GroundX
agentic processing substrate to run on; `processLevel: none` skips the reprocessing that
extraction workflows depend on. See §15 in `02-documents.md`, `06-workflows.md`, and
`guides/09-workflows.md`.

## 11. Updating and managing documents after ingest

To replace or re-process an ingested document, use `document_update` with the
`documentId`. To copy documents between buckets, use `documents_copy`. To remove
documents, use `documents_delete`. All three operations are also asynchronous and
return a `processId`. See §6, §7, and §8 in 02-documents.md for details.

## 12. Pre-upload validation and file preparation

Check every file against the recommended limits before uploading. Submitting files that
exceed these limits either fails outright (size) or produces degraded retrieval quality
(very long documents dilute chunk relevance). See §4 in 08-errors-and-limits.md for the
full limits table.

**Recommended limits to enforce at upload time:**
- File size: 25 MB or less
- Page count: 200 pages or less (PDFs, PPTX, DOCX)

### Splitting oversized documents

Splitting is an implementation detail that must be invisible to end users. From the
user's perspective, they uploaded one document; from GroundX's perspective, it is
stored as multiple documents. The UI must reconcile this by treating all parts as the
same file — the same display name, the same access control, the same attribution in
search results.

If a document exceeds either limit, split it before uploading. Splitting at logical
boundaries produces better retrieval than splitting at arbitrary page intervals — a
300-page technical manual split at chapter boundaries yields 10–15 coherent documents,
while a page-count split may cut a chapter mid-sentence.

**Finding split points with an LLM.** Extract a table of contents or outline from the
document (most PDF libraries expose bookmark trees; DOCX files have heading paragraphs),
then ask an LLM to suggest chapter or section boundaries that keep each part under the
page limit. The LLM can group thin sections together and split thick ones, aiming for
even-ish chunks that each make sense as a standalone unit.

**Reducing file size for image-heavy documents.** PDFs that are primarily scanned pages
or high-resolution images can often be reduced significantly without affecting OCR
quality. Downscaling embedded images to 150–200 DPI is typically sufficient for
GroundX's X-Ray pipeline. Python's `pymupdf` (fitz) and `pikepdf` both support
image recompression in-place.

### Metadata for split documents

Every part must be ingested with identical `filter` and `searchData` content fields —
the same values the original unsplit document would have carried. Access control and
tenant isolation are enforced through `filter`, so all parts must match exactly. Any
field the UI uses to display or attribute results (title, author, category, etc.) must
also be the same across all parts.

In addition, each part should carry three `searchData` fields that the UI uses to
group parts back into a single logical document:

| Field | Value |
|---|---|
| `splitSourceId` | A stable identifier for the original document — a UUID or deterministic hash of the original file name and upload context. Identical across all parts. |
| `splitPart` | 1-based integer index of this part within the set. |
| `splitTotal` | Total number of parts the original document was split into. |

Example for a four-part split of `annual-report-2024.pdf`:

```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "...",
      "fileName": "annual-report-2024.pdf",
      "fileType": "pdf",
      "filter": { "department": "finance", "roles": ["director"] },
      "searchData": {
        "title": "Annual Report 2024",
        "author": "Finance Team",
        "splitSourceId": "a3f9c1d2-84b7-4e0a-9c11-2d7f3b8e5a60",
        "splitPart": 1,
        "splitTotal": 4
      }
    }
  ]
}
```

All four parts use the same `fileName` ("annual-report-2024.pdf"), the same `filter`,
and the same `title` and `author` — so search results and source cards display the
original document's identity regardless of which part matched. The `splitSourceId`,
`splitPart`, and `splitTotal` fields let the UI detect that a result came from a split
document and suppress duplicate attributions when multiple parts surface in the same
search.

### Pre-upload checklist

Before calling the pre-signed upload service (§5):

1. Measure file size — reject or split if over 25 MB
2. Count pages for PDFs, PPTX, and DOCX — reject or split if over 200 pages
3. Confirm `fileType` matches the actual file extension (§2)
4. If the file was split: apply identical `filter` and content `searchData` to all
   parts, and add `splitSourceId`, `splitPart`, and `splitTotal` to each part

## 13. Python and TypeScript SDK convenience methods

The GroundX Python and TypeScript SDKs provide higher-level `ingest()` and
`ingest_directory()` methods that sit above the raw REST API. These handle local file
routing, batching, and polling internally and are the recommended way to ingest from
application code.

### client.ingest()

Unified ingest for both local and remote files. Accepts a mix of local paths and URLs
in the same call — the SDK automatically routes local paths through the pre-signed URL
service (§5) and submits everything via `document_ingestremote`.

**Parameters:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `documents` | yes | — | Array of `Document` objects (see below) |
| `wait_for_complete` | no | `false` | Python only. If `true`, blocks until all documents reach `complete` or `error`, rendering a progress bar. |
| `batch_size` | no | `10` | Python only. Documents per ingest request; 1–50. |
| `upload_api` | no | EyeLevel API | Custom pre-signed URL endpoint (§5). |
| `callback_url` | no | — | Endpoint to receive processing event POSTs. |
| `callback_data` | no | — | String returned unchanged with each callback notification. |

**`Document` object fields:**

| Field | Required | Description |
|---|---|---|
| `bucket_id` / `bucketId` | yes | Target bucket |
| `file_path` / `filePath` | yes | Local filesystem path or public URL |
| `file_name` / `fileName` | no | Display name for the file |
| `file_type` / `fileType` | no | File extension without dot (e.g. `"pdf"`); inferred if omitted |
| `filter` | no | Pre-filter metadata object — see §7 |
| `process_level` / `processLevel` | no | `"full"` or `"none"` — see §10 |
| `search_data` / `searchData` | no | Search-time metadata object — see §7 |

**Python:**
```python
from groundx import Document, GroundX

client = GroundX(api_key="YOUR_API_KEY")

response = client.ingest(
    documents=[
        Document(
            bucket_id=1234,
            file_path="https://example.com/report.pdf",
            file_name="report.pdf",
            file_type="pdf",
        ),
        Document(
            bucket_id=1234,
            file_path="/local/path/appendix.docx",
            file_name="appendix.docx",
            file_type="docx",
            search_data={"department": "legal", "year": "2024"},
        ),
    ]
)
process_id = response.ingest.process_id
```

**TypeScript:**
```typescript
import { GroundXClient } from "groundx";

const client = new GroundXClient({ apiKey: "YOUR_API_KEY" });

const response = await client.ingest([
    {
        bucketId: 1234,
        filePath: "https://example.com/report.pdf",
        fileName: "report.pdf",
        fileType: "pdf",
    },
    {
        bucketId: 1234,
        filePath: "/local/path/appendix.docx",
        fileName: "appendix.docx",
        fileType: "docx",
        searchData: { department: "legal", year: "2024" },
    },
]);
```

The response includes `ingest.processId` and `ingest.status`. Poll
`documents.get_processing_status_by_id` to track progress unless `wait_for_complete`
is set to `true`.

### client.ingest_directory()

**Python SDK only.** Bulk-uploads all supported files in a directory tree to a bucket.
Crawls the directory recursively, batches files, uploads each batch via the pre-signed
URL service, and polls until each batch completes before starting the next. Renders a
`tqdm` progress bar during execution.

**Parameters:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `bucket_id` | yes | — | Target bucket |
| `path` | yes | — | Local directory path to crawl |
| `batch_size` | no | `10` | Files per ingest request; 1–50 (subscription) or 1–25 (trial) |
| `upload_api` | no | EyeLevel API | Custom pre-signed URL endpoint (§5) |

```python
from groundx import GroundX

client = GroundX(api_key="YOUR_API_KEY")

client.ingest_directory(
    bucket_id=1234,
    path="/path/to/documents/",
    batch_size=10,
)
```

`ingest_directory` does not return a single `processId` — it submits multiple batches
sequentially and polls each internally. It is a blocking call: it does not return until
all files in the directory have been submitted and their batches have completed. Use it
for one-time bulk loads or offline ingestion pipelines; it is not suited to production
request handlers.
