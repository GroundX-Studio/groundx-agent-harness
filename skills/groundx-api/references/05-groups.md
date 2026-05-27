# Groups

This reference covers the seven group operations: creating a group (optionally with a
new bucket), listing groups, getting a group, renaming a group, adding a bucket to a
group, removing a bucket from a group, and deleting a group.

## 1. Group overview

A group is a named collection of buckets. Searching a group searches all buckets
associated with it in a single query. Groups enable logical partitioning above the
bucket level — for example, grouping buckets by project, customer, or topic.

Buckets and groups have a many-to-many relationship: one bucket can belong to multiple
groups, and one group can contain multiple buckets.

A group object contains:

| Field | Description |
|---|---|
| `groupId` | Integer identifier assigned at creation |
| `name` | Display name; mutable via `group_update` |
| `buckets` | Array of bucket objects associated with this group |
| `fileCount` | Total documents across all associated buckets |
| `fileSize` | Total storage across all associated buckets |
| `created` | Creation timestamp in RFC 3339 format |
| `updated` | Last-updated timestamp in RFC 3339 format |

## 2. group_create / POST /v1/group

Create a new group. Optionally supply `bucketName` to simultaneously create a new bucket
and associate it with the group in a single call.

**MCP (group only):**
```json
{ "name": "legal-documents" }
```

**MCP (group + new bucket):**
```json
{ "name": "legal-documents", "bucketName": "contracts-2026" }
```
Tool: `group_create` → returns `group.groupId`

**REST:**
```http
POST /v1/group
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "name": "legal-documents" }
```

**Response:**
```json
{
  "group": {
    "groupId": 42,
    "name": "legal-documents",
    "buckets": [],
    "fileCount": 0,
    "fileSize": "0B",
    "created": "2026-01-15T10:00:00.000Z",
    "updated": "2026-01-15T10:00:00.000Z"
  }
}
```

If `bucketName` was provided, `buckets` will contain the newly created bucket.

**Errors:** 400 — invalid body parameter.

## 3. group_list / GET /v1/group

List all groups in the account.

**MCP:**
```json
{ "n": 20 }
```
Tool: `group_list`

**REST:**
```http
GET /v1/group?n=20
X-API-Key: YOUR_API_KEY
```

**Query parameters:**

| Parameter | Description |
|---|---|
| `n` | Maximum groups to return; accepts 1–100, default 20 |
| `nextToken` | Pagination cursor from a previous response |

**Response:** `{ "groups": [...], "count": N, "total": N, "remaining": N }`

## 4. group_get / GET /v1/group/{groupId}

Retrieve a single group by its `groupId`, including all associated buckets.

**MCP:**
```json
{ "groupId": 42 }
```
Tool: `group_get`

**REST:**
```http
GET /v1/group/42
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "group": { ... } }` — full group object as described in §1.

**Errors:** 400 — invalid group ID; 401 — unauthorized to access that group.

## 5. group_update / PUT /v1/group/{groupId}

Rename a group. Only the name is mutable.

**MCP:**
```json
{ "groupId": 42, "newName": "litigation-2026" }
```
Tool: `group_update`

**REST:**
```http
PUT /v1/group/42
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "newName": "litigation-2026" }
```

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `groupId` | yes | ID of the group to rename (path) |
| `newName` | yes | New display name for the group (body) |

**Response:** Full updated group object.

**Errors:** 400 — invalid body parameter; 401 — unauthorized to update that group.

## 6. group_addbucket / POST /v1/group/{groupId}/bucket/{bucketId}

Associate an existing bucket with a group using `groupId` and `bucketId`. The bucket
must already exist (see 04-buckets.md). This is a path-only operation with no request
body.

**MCP:**
```json
{ "groupId": 42, "bucketId": 1234 }
```
Tool: `group_addbucket`

**REST:**
```http
POST /v1/group/42/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

**Errors:** 400 — invalid path parameter; 401 — unauthorized to update that group.

## 7. group_removebucket / DELETE /v1/group/{groupId}/bucket/{bucketId}

Remove the association between a bucket and a group using `groupId` and `bucketId`.
The bucket is not deleted — only the group membership is removed. Other group
memberships the bucket may have are unaffected.

**MCP:**
```json
{ "groupId": 42, "bucketId": 1234 }
```
Tool: `group_removebucket`

**REST:**
```http
DELETE /v1/group/42/bucket/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

**Errors:** 400 — invalid path parameter; 401 — unauthorized to update that group.

## 8. group_delete / DELETE /v1/group/{groupId}

Delete the group identified by `groupId`. The buckets associated with the group are
not deleted — only the group itself and its bucket associations are removed.

**MCP:**
```json
{ "groupId": 42 }
```
Tool: `group_delete`

**REST:**
```http
DELETE /v1/group/42
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

**Errors:** 400 — invalid group ID; 401 — unauthorized to delete that group.
