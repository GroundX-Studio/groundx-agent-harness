# Buckets

This reference covers the five bucket operations: creating, listing, getting, renaming,
and deleting buckets.

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

Create a new bucket. The `name` must be provided. The response includes the assigned
`bucketId`, which must be saved and used in subsequent ingest calls.

**MCP:**
```json
{ "name": "my-bucket" }
```
Tool: `bucket_create` → returns `bucket.bucketId`

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

**MCP:**
```json
{ "n": 20 }
```
Tool: `bucket_list`

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

**MCP:**
```json
{ "bucketId": 1234 }
```
Tool: `bucket_get`

**REST:**
```http
GET /v1/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "bucket": { ... } }` — full bucket object as described in §1.

**Errors:** 400 — invalid bucket ID; 401 — unauthorized to access that bucket.

## 5. bucket_update / PUT /v1/bucket/{bucketId}

Rename a bucket. Only the name is mutable; `bucketId` and document contents are
unchanged.

**MCP:**
```json
{ "bucketId": 1234, "newName": "q1-contracts" }
```
Tool: `bucket_update`

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
| `newName` | yes | New display name for the bucket (body) |

**Response:** `{ "bucket": { "bucketId": 1234, "name": "q1-contracts" } }`

**Errors:** 400 — invalid body parameter; 401 — unauthorized to update that bucket.

## 6. bucket_delete / DELETE /v1/bucket/{bucketId}

Delete the bucket identified by `bucketId`. This removes the bucket and all documents
it contains. The operation is not recoverable.

**MCP:**
```json
{ "bucketId": 1234 }
```
Tool: `bucket_delete`

**REST:**
```http
DELETE /v1/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

**Errors:** 400 — invalid bucket ID; 401 — unauthorized to delete that bucket.
