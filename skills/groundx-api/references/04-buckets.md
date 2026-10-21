# Buckets

This reference covers bucket lifecycle operations. Read `13-file-access.md` for initial
`fileAccess`, inherited readback, policy updates and private `file-upload`.

## 1. Bucket overview

A bucket is the primary storage container for ingested documents. Every document is
ingested into a bucket. Buckets are identified by an integer `bucketId` assigned at
creation. All ingest and search operations that target a set of documents do so via
`bucketId` or `groupId` (see 05-groups.md for groups).

A bucket object contains:

| Field | Description |
|---|---|
| `bucketId` | Integer identifier assigned at creation |
| `name` | Display name set at creation; mutable via `bucket_update` |
| `fileCount` | Number of documents currently in the bucket |
| `fileSize` | Total size of documents in the bucket (e.g. `"3.1GB"`) |
| `created` | Creation timestamp in RFC 3339 format |
| `updated` | Last-updated timestamp in RFC 3339 format |

## 2. bucket_create / POST /v1/bucket

Create a new bucket. The `name` must be provided. Optional `fileAccess` is applied at
creation omitted/null inherits. Do not create public then
update to protected. The response includes the assigned
`bucketId`, which must be saved and used in subsequent ingest calls.

**MCP discovery:** List operations and describe `Bucket_create` first, then:
```json
{
  "operationId": "Bucket_create",
  "args": {
    "name": "my-bucket"
  }
}
```
Tool: `call_operation` → returns `bucket.bucketId`

**REST:**
```http
POST /v1/bucket
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "name": "my-bucket" }
```

**Response:**
```json
{
  "bucket": {
    "bucketId": 1234,
    "name": "my-bucket",
    "fileCount": 0,
    "fileSize": "0B",
    "created": "2026-01-15T10:00:00.000Z",
    "updated": "2026-01-15T10:00:00.000Z"
  }
}
```

**Errors:** 400 — invalid body parameter.

## 3. bucket_list / GET /v1/bucket

List all buckets in the account.

**MCP discovery:** List operations and describe `Bucket_list` first, then:
```json
{
  "operationId": "Bucket_list",
  "args": {
    "n": 20
  }
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/bucket?n=20
X-API-Key: YOUR_API_KEY
```

**Query parameters:**

| Parameter | Description |
|---|---|
| `n` | Maximum buckets to return; accepts 1–100, default 20 |
| `nextToken` | Pagination cursor from a previous response |

**Response:**
```json
{
  "buckets": [...],
  "count": 5,
  "total": 12,
  "remaining": 7
}
```

`remaining` indicates how many more buckets exist beyond the current page. Use
`nextToken` to fetch subsequent pages.

## 4. bucket_get / GET /v1/bucket/{bucketId}

Retrieve a single bucket by its `bucketId`.

**MCP discovery:** List operations and describe `Bucket_get` first, then:
```json
{
  "operationId": "Bucket_get",
  "args": {
    "bucketId": 1234
  }
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "bucket": { ... } }` — full bucket object as described in §1.

**Errors:** 400 — invalid bucket ID; 401 — unauthorized to access that bucket.

## 5. bucket_update / PUT /v1/bucket/{bucketId}

Rename a bucket or change its file-access override in separate requests. A policy-only write need not
include `newName`. Send only the desired policy; no revision lookup is needed. Explicit `fileAccess: null` clears the override. See `13-file-access.md`.

**MCP discovery:** List operations and describe `Bucket_update` first, then:
```json
{
  "operationId": "Bucket_update",
  "args": {
    "bucketId": 1234,
    "newName": "q1-contracts"
  }
}
```
Tool: `call_operation`

**REST:**
```http
PUT /v1/bucket/1234
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "newName": "q1-contracts" }
```

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `bucketId` | yes | ID of the bucket to rename (path) |
| `newName` | no | New display name for the bucket (body) |

**Response:** `{ "bucket": { "bucketId": 1234, "name": "q1-contracts" } }`

**Errors:** 400 — invalid body parameter; 401 — unauthorized to update that bucket.

## 6. bucket_delete / DELETE /v1/bucket/{bucketId}

Delete the bucket identified by `bucketId`. This removes the bucket and all documents
it contains. The operation is not recoverable.

**MCP discovery:** List operations and describe `Bucket_delete` first, then:
```json
{
  "operationId": "Bucket_delete",
  "args": {
    "bucketId": 1234
  }
}
```
Tool: `call_operation`

**REST:**
```http
DELETE /v1/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

**Errors:** 400 — invalid bucket ID; 401 — unauthorized to delete that bucket.

## Private upload reservation

`POST /v1/bucket/{bucketId}/file-upload` (`Buckets_fileUpload`) accepts `fileName` and
`fileType`, returns 201 `{ uploadId, uploadUrl, hostedUrl, expiresAt, method, headers }`,
and requires `groundx:write` through MCP discovery. Reserve before sending protected
bytes. PUT to native storage, then submit `hostedUrl` through existing ingest. Read
`13-file-access.md` for ownership, expiry and per-file policy requirements.
