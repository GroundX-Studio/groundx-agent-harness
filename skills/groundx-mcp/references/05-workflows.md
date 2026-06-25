# GroundX MCP — End-to-End Document Workflow

## 1. Overview

This reference describes the standard end-to-end workflow for ingesting a document and
making it searchable through the GroundX MCP server. Every step uses only the default
tools from this skill (`skills/groundx-mcp/references/02-default-tools.md`). No other
GroundX skill is required.

The workflow is:

1. Create a bucket to hold your documents.
2. Optionally create a group and add the bucket to it (enables cross-bucket search).
3. Ingest a remote document into the bucket.
4. Poll until processing is complete — ingest is asynchronous.
5. Search the bucket or group.

All tool names below are verbatim from `skills/groundx-mcp/references/02-default-tools.md`.
Do not abbreviate or invent variants. The required scope for each step is stated inline and
summarized in the table at the end of this document.

---

## 2. Step 1 — Create a bucket

**Required scope:** `groundx:write`

A bucket is the primary storage container for your documents. Call `bucket_create` with a
human-readable name. Save the `bucketId` returned in the response — it is required in every
subsequent step.

```json
bucket_create({ "name": "my-documents" })
```

The response includes a `bucketId` (for example `789`). Save it.

---

## 3. Step 2 — Optionally create a group and add the bucket

**Required scope for both calls:** `groundx:write`

Groups enable search across multiple buckets in a single query. If you only have one bucket
or do not need cross-bucket search, skip this step.

### 3.1 Create the group

```json
group_create({ "name": "my-group" })
```

The response includes a `groupId` (for example `456`). Save it.

### 3.2 Add the bucket to the group

```json
group_addbucket({ "groupId": 456, "bucketId": 789 })
```

Replace `456` and `789` with the actual `groupId` and `bucketId` from the previous calls.
After this call, search queries targeting the group will include documents in the bucket.

---

## 4. Step 3 — Ingest a remote document

**Required scope:** `groundx:ingest`

Call `document_ingestremote` to submit a document for processing. The document must be
reachable via a public URL at the time of ingest. Provide metadata such as `title` to make
results more useful in search responses.

```json
document_ingestremote({
  "bucketId": 789,
  "ingestRemoteDocumentRequest": {
    "documents": [
      {
        "bucketId": 789,
        "sourceUrl": "https://example.com/my-document.pdf",
        "metadata": {
          "title": "My Document"
        }
      }
    ]
  }
})
```

Replace `789` with your actual `bucketId` and replace the `sourceUrl` and `title` with your
document's values.

The response includes a `processId` (for example `"abc123"`). Save it. Ingest is
asynchronous — the document is not searchable yet.

---

## 5. Step 4 — Poll for completion

**Required scope:** `groundx:ingest`

**Do not skip this step.** Ingest is asynchronous. The document is not indexed and will not
appear in search results until its status is `complete`. Query `document_getprocessingstatusbyid`
with the `processId` from Step 3 and repeat until the status field shows `complete`.

```json
document_getprocessingstatusbyid({ "processId": "abc123" })
```

Replace `"abc123"` with the actual `processId` from the ingest response.

- If the status is `complete`, the document is indexed and searchable. Proceed to Step 5.
- If the status is `error`, inspect the response for details before retrying.
- For any other status (for example `queued` or `processing`), wait a few seconds and poll
  again. There is no server-side webhook — polling is required.

---

## 6. Step 5 — Search

**Required scope:** `groundx:write`

Once the processing status is `complete`, call `search_content` to query within a specific
bucket or group. Pass the `bucketId` or `groupId` as `id`.

```json
search_content({
  "id": 789,
  "searchContentRequest": {
    "query": "your query"
  }
})
```

Replace `789` with your `bucketId` or `groupId`, and replace `"your query"` with the actual
search string.

Alternatively, use `search_documents` to search across all documents without specifying a
bucket or group target:

```json
search_documents({
  "searchDocumentsRequest": {
    "query": "your query"
  }
})
```

---

## 7. Scope summary

| Step | Tool | Required scope |
|---|---|---|
| 1. Create bucket | `bucket_create` | `groundx:write` |
| 2a. Create group | `group_create` | `groundx:write` |
| 2b. Add bucket to group | `group_addbucket` | `groundx:write` |
| 3. Ingest document | `document_ingestremote` | `groundx:ingest` |
| 4. Poll for completion | `document_getprocessingstatusbyid` | `groundx:ingest` |
| 5a. Search by bucket or group | `search_content` | `groundx:write` |
| 5b. Search across documents | `search_documents` | `groundx:write` |

A session with only `groundx:read` scope cannot complete this workflow. `groundx:read`
grants access only to `bucket_list`, `group_list`, and `health_get` from the default tool
set. See `skills/groundx-mcp/references/02-default-tools.md` for the full visibility table.

---

## 8. Standalone note

This workflow is fully supported with the `groundx-mcp` skill alone. No other GroundX skill
is required to complete it. If you need REST or SDK fallback — for example, to drive ingest
programmatically from a backend service — see the `groundx-api` skill for the REST base URL,
SDK setup, and endpoint operation details.
