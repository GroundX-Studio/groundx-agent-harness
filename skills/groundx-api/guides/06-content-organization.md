# Content Organization

How to structure content in GroundX: the recommended single-bucket model, how to
use the `filter` field to represent any organizational hierarchy, and the narrow
role of groups for combining a small number of distinct content corpora.

## 1. Core concepts

**Bucket** — the primary storage unit. Every ingested document lives in exactly one
bucket, identified by an integer `bucketId`. All ingest and search operations target
a bucket (or group) directly. See §1 in 04-buckets.md.

**Group** — a named collection of 1–4 buckets searched together in a single call.
See §3 below for the performance constraint that limits group size. See §1 in
05-groups.md.

**`filter` field** — a JSON object attached to each document at ingest (or updated
later via `document_update`). Applied as a pre-filter in OpenSearch before any
search query runs — documents not matching the filter are excluded before the
search even executes. The primary mechanism for all logical organization within a
bucket. See `guides/07-filter-field.md` for the complete reference.

> **Terminology note:** older GroundX documentation uses the term "project" for
> what the current API calls a "group". The API uses `groupId` and `group_*` tool
> names throughout. "Project" does not appear in any current API operation.

## 2. Recommended approach: one bucket, filter-based organization

**Use a single bucket. Organize with the `filter` field.**

When a single bucket is searched, GroundX first applies the `filter` pre-filter in
OpenSearch, then runs its bigram-style multifield weighted query to select up to 100
candidate chunks, then passes those to the semantic reranker. Every logical subset —
project, folder, tenant, role tier — is enforced in OpenSearch before any query
runs, so the reranker always operates on the best available candidates within
whatever scope the search needs.

Splitting content across many buckets or groups degrades reranker quality (see §3)
and adds operational overhead. The `filter` field can represent any organizational
concept — projects, folders, access roles, org hierarchy, versioning — without
sacrificing search quality. Filter metadata is updatable after ingest, so
reorganizing content is a metadata operation, not a re-ingest.

## 3. Group performance constraint

When `search_content` runs against a **single bucket**, GroundX retrieves up to 100
candidate chunks and passes all of them to the semantic reranker, which returns the
top 20. The reranker operates at maximum depth.

When a **group** is searched, the 100-candidate budget is divided across all member
buckets. More buckets means fewer candidates per bucket entering the reranker. Search
quality and latency degrade noticeably beyond 4–5 buckets in a group.

**Groups should contain 1–4 buckets.** For anything more complex, use filter-based
organization within a single bucket.

## 4. Portfolio example: full hierarchy with RBAC

This example shows how a SaaS product can represent a complete content hierarchy —
tenants, portfolios, projects, folders — plus role-based access control, all within
a single bucket using filter fields.

### 4.1 Hierarchy definition

```
Tenant        (top-level customer account)
  └── Portfolio  (a group of related projects owned by the tenant)
        └── Project   (a unit of work within a portfolio)
              └── Folder    (a named collection of documents within a project)
```

All of this lives in one bucket. Portfolios, projects, and folders are not GroundX
buckets or groups — they are values in each document's `filter` field.

### 4.2 Filter schema

Every document carries the full path from tenant down to folder, plus RBAC fields:

```json
{
  "filter": {
    "tenant":    "tenant-acme",
    "portfolio": "portfolio-alpha",
    "project":   "proj-001",
    "folder":    "folder-specs",
    "roles":     ["member", "editor", "admin"],
    "access":    "internal"
  }
}
```

**Field guide:**

| Field | Type | Purpose |
|---|---|---|
| `tenant` | string | Top-level isolation — always included in every search filter |
| `portfolio` | string | Portfolio ID — scope search to one portfolio |
| `project` | string | Project ID — scope search to one project |
| `folder` | string | Folder ID — scope search to one folder |
| `roles` | list of strings | Which roles can see this document |
| `access` | string | Access tier: `"public"`, `"internal"`, `"confidential"` |

### 4.3 Ingesting with filter metadata

```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/spec-v2.pdf",
      "fileName": "spec-v2.pdf",
      "fileType": "pdf",
      "filter": {
        "tenant":    "tenant-acme",
        "portfolio": "portfolio-alpha",
        "project":   "proj-001",
        "folder":    "folder-specs",
        "roles":     ["member", "editor", "admin"],
        "access":    "internal"
      }
    }
  ]
}
```
Tool: `document_ingestremote` → `ingest.processId`

### 4.4 Searching with a filter

Pass the appropriate filter expression in the search request to scope it to any
level of the hierarchy.

**Search within a specific folder (user has `"editor"` role):**

```json
{
  "id": 1234,
  "query": "What are the API rate limits?",
  "filter": {
    "$and": [
      { "tenant":    "tenant-acme" },
      { "portfolio": "portfolio-alpha" },
      { "project":   "proj-001" },
      { "folder":    "folder-specs" },
      { "roles":     { "$in": ["editor"] } },
      { "access":    { "$in": ["public", "internal"] } }
    ]
  }
}
```
Tool: `search_content`

**Search across all folders in a project:**

```json
{
  "id": 1234,
  "query": "deployment checklist",
  "filter": {
    "$and": [
      { "tenant":    "tenant-acme" },
      { "portfolio": "portfolio-alpha" },
      { "project":   "proj-001" },
      { "roles":     { "$in": ["member"] } }
    ]
  }
}
```

**Search across all projects in a portfolio (admin user, all access tiers):**

```json
{
  "id": 1234,
  "query": "Q3 status",
  "filter": {
    "$and": [
      { "tenant":    "tenant-acme" },
      { "portfolio": "portfolio-alpha" },
      { "roles":     { "$in": ["admin"] } }
    ]
  }
}
```

**Search the entire tenant (admin, no portfolio or project scope):**

```json
{
  "id": 1234,
  "query": "security policy",
  "filter": {
    "$and": [
      { "tenant": "tenant-acme" },
      { "roles":  { "$in": ["admin"] } }
    ]
  }
}
```

The tenant filter is always required. Portfolio, project, and folder filters are
additive — omit them to broaden scope, include them to narrow it. The `roles` filter
is always required for RBAC enforcement.

### 4.5 Updating filter metadata

Moving a document to a different folder, changing its access tier, or updating which
roles can see it requires only a metadata update — no re-ingest:

```json
{
  "documentId": "doc-uuid",
  "filter": {
    "tenant":    "tenant-acme",
    "portfolio": "portfolio-alpha",
    "project":   "proj-001",
    "folder":    "folder-archive",
    "roles":     ["admin"],
    "access":    "confidential"
  }
}
```
Tool: `document_update` → `ingest.processId` (async — poll to confirm)

See §11 in 02-documents.md for the full `document_update` parameter table.

## 5. Using groups for cross-portfolio search

GroundX groups are the right tool when a small number of distinct content corpora
need to be searched together. In the portfolio model, groups address the case where
a user needs to search across multiple tenants' portfolios simultaneously — for
example, an admin chat interface that spans up to 4–5 portfolios stored in separate
buckets for hard isolation.

**When to use a separate bucket per portfolio:**
- The portfolio requires hard data isolation (different ingest pipelines, different
  access credentials, different processing workflows)
- The portfolio may be deleted or transferred independently

**When to keep portfolios in one bucket:**
- All portfolios belong to the same tenant and isolation via filter is acceptable
- You want full reranker depth on every search

**If you do use separate buckets, create a group for cross-portfolio search:**

```json
{ "name": "acme-all-portfolios", "bucketName": "portfolio-alpha" }
```
Tool: `group_create` → `group.groupId`

Then add additional portfolio buckets (keep total to 4–5 or fewer):

```json
{ "groupId": 50, "bucketId": 11 }
```
Tool: `group_addbucket`

Search across all portfolios in the group:

```json
{
  "id": 50,
  "query": "Q3 status across all portfolios",
  "filter": { "tenant": "tenant-acme" }
}
```

**Strong recommendation:** keep groups to 4–5 buckets maximum. If you have more
portfolios than that, keep them in a single bucket with filter-based isolation rather
than adding more buckets to a group.

## 6. Scoping search

`search_content` accepts either a `bucketId` or a `groupId` as `id`:

```json
{ "id": 1234, "query": "..." }
```

Every search is scoped to a bucket or group — there is no account-wide search.
`search_documents` accepts an explicit list of `documentIds` and is unaffected by
bucket or group boundaries. See §1–2 in 03-search.md for search parameters.

## 7. Managing buckets and groups

**Create a group and simultaneously create a new bucket:**
```json
{ "name": "legal-documents", "bucketName": "contracts-2026" }
```
Tool: `group_create` → `group.groupId`

**Add an existing bucket to a group:**
```json
{ "groupId": 50, "bucketId": 10 }
```
Tool: `group_addbucket`

**Remove a bucket from a group (does not delete the bucket):**
```json
{ "groupId": 50, "bucketId": 10 }
```
Tool: `group_removebucket`

See §2–7 in 05-groups.md for the full group operation reference and §2–6 in
04-buckets.md for bucket CRUD.

## 8. Workflow assignment by scope

Workflows control the processing pipeline applied during ingest. They can be assigned
at three levels — more specific assignments override broader ones:

```
account level         → default for all ingest
    ↓ overridden by
group or bucket level → applies to files ingested into that group or bucket
    ↓ overridden by
processLevel field    → per-document control over processing depth
```

**Assign a workflow to the account (default for all ingest):**
```json
{ "workflowId": "workflow-uuid" }
```
Tool: `workflow_add_to_account`

**Assign a workflow to a specific bucket or group:**
```json
{ "id": 1234, "workflowId": "workflow-uuid" }
```
Tool: `workflow_add_to_id`

See §1.1 in 06-workflows.md for the full scope hierarchy and workflow CRUD operations.
