# The Filter Field

The `filter` field is a per-document JSON object that enables pre-filtering of search
candidates before the semantic reranker runs. It is the primary mechanism for
organizing documents within a bucket into logical subsets and for enforcing access
control. This guide covers what `filter` is, how to design its schema, how to set
and update it, and a full catalog of use cases.

## 1. What the filter field does

When a search request includes a `filter` expression, GroundX evaluates that
expression against every document's stored `filter` metadata in OpenSearch before
any search query runs. Only documents whose metadata matches are included in the
OpenSearch candidate set. Documents without matching metadata are excluded entirely
before the bigram-style multifield weighted query even executes.

This makes the `filter` field the right place for any criterion that should control
whether a document is eligible to appear in results at all: tenant identity, access
roles, organizational hierarchy, content version, publication status, and so on.

The `filter` field is distinct from `searchData`:
- **`filter`** — controls document eligibility via pre-filtering at search time
- **`searchData`** — contextual metadata fed into the ranking model and returned
  alongside chunks in `search.results[n].searchData`; does not control inclusion

See §7 in 02-ingest-patterns.md for the full field comparison.

## 2. Setting filter metadata at ingest

Attach the `filter` object to each document when ingesting via `document_ingestremote`.
For local files, set `filter` in the `document_ingestremote` call that follows the
pre-signed upload (see §5 in 02-ingest-patterns.md):

```json
{
  "documents": [
    {
      "bucketId": 1234,
      "sourceUrl": "https://example.com/policy-v2.pdf",
      "fileName": "policy-v2.pdf",
      "fileType": "pdf",
      "filter": {
        "tenant": "acme",
        "department": "legal",
        "roles": ["director", "executive"],
        "security_level": 2,
        "status": "published",
        "version": 2
      }
    }
  ]
}
```

**Supported value types:**
- String: `"legal"`, `"published"`
- Number (64-bit float): `2`, `3.14`
- Boolean: `true`, `false`
- List of strings or numbers: `["director", "executive"]`
- Nested objects following the same rules

**Limit:** 40 KB total per document. Filter metadata is not available on
`document_crawlwebsite` (crawls support `searchData` only).

## 3. Updating filter metadata after ingest

Filter metadata can be updated at any time without re-ingesting the document:

```json
{
  "documentId": "doc-uuid",
  "filter": {
    "tenant": "acme",
    "department": "legal",
    "status": "archived",
    "version": 3
  }
}
```

Tool: `document_update` → `ingest.processId` (async — poll to confirm)

This makes filter-based organization resilient to change: moving a document between
folders, promoting a draft to published, revoking a role, or changing a version label
are all metadata updates rather than re-ingests. See §11 in 02-documents.md for the
full `document_update` parameter table.

## 4. Query syntax at search time

Pass a `filter` expression in the search request. The expression uses a subset of
MongoDB query operators. A bare string value is an implicit `$eq`:

```json
{ "tenant": "acme" }
```

**Available operators:**

| Operator | Description | Types |
|---|---|---|
| `$eq` | Equal to | String, number, boolean |
| `$ne` | Not equal to | String, number, boolean |
| `$gt` / `$gte` | Greater / greater-or-equal | Number |
| `$lt` / `$lte` | Less / less-or-equal | Number |
| `$in` | Value in array | String, number |
| `$nin` | Value not in array | String, number |
| `$exists` | Field exists | String, number, boolean |
| `$and` | Logical AND of clauses | — |
| `$or` | Logical OR of clauses | — |

For list fields, the query checks whether the queried value is contained in the list.
`{ "roles": "director" }` matches a document with `roles: ["director", "executive"]`.

See §5 in 06-content-organization.md for a complete worked example combining filter fields with RBAC and org hierarchy at search time.

## 5. Use cases

### 5.1 Multi-tenant isolation

Each document carries a tenant identifier. Every search always includes the tenant
filter, enforcing that one tenant cannot see another's content.

**Ingest:**
```json
{ "filter": { "tenant": "acme" } }
```

**Search:**
```json
{
  "id": 1234,
  "query": "refund policy",
  "filter": { "tenant": "acme" }
}
```

This keeps all tenants in a single bucket, giving the reranker a larger and more
diverse candidate pool than per-tenant buckets would provide.

### 5.2 Role-based access control (RBAC)

Attach the roles (or permission levels) that are allowed to see a document. At search
time, filter to only documents the requesting user's roles can access.

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "roles": ["admin", "legal"]
  }
}
```

**Search as a user with role `"legal"`:**
```json
{
  "id": 1234,
  "query": "contract terms",
  "filter": {
    "$and": [
      { "tenant": "acme" },
      { "roles": { "$in": ["legal"] } }
    ]
  }
}
```

Because list fields check membership, a document tagged `["admin", "legal"]` matches
a filter for `"legal"`. Documents without `"legal"` in their roles list are excluded.

### 5.3 Tiered security levels

Use a numeric `security_level` field to express clearance tiers. Users at a given
level can see everything at or below their level.

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "security_level": 3
  }
}
```

**Search as a level-2 user:**
```json
{
  "filter": {
    "$and": [
      { "tenant": "acme" },
      { "security_level": { "$lte": 2 } }
    ]
  }
}
```

Combining `security_level` with a `roles` list gives a two-axis access model:
a document must match both the role list and the level threshold to be returned.

### 5.4 Content organization: projects and folders

Map application-level hierarchy directly to filter fields. A UI that exposes
"projects" with "folders" of documents inside them can use:

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "project": "proj-123",
    "folder": "folder-456"
  }
}
```

**Search a specific folder:**
```json
{ "filter": { "tenant": "acme", "project": "proj-123", "folder": "folder-456" } }
```

**Search an entire project:**
```json
{ "filter": { "tenant": "acme", "project": "proj-123" } }
```

Because filter metadata is updatable, documents can be moved between folders or
reassigned to different projects without re-processing.

### 5.5 Organization hierarchy

Model department, team, region, or any org-chart concept. Search can be scoped
anywhere in the hierarchy.

**Ingest:**
```json
{
  "filter": {
    "tenant": "globocorp",
    "region": "emea",
    "department": "finance",
    "team": "treasury"
  }
}
```

**Search the entire finance department across all regions:**
```json
{ "filter": { "tenant": "globocorp", "department": "finance" } }
```

**Search only EMEA finance:**
```json
{ "filter": { "tenant": "globocorp", "region": "emea", "department": "finance" } }
```

### 5.6 Document versioning and status

Track document lifecycle and version history without duplicating content across
buckets. Use a `status` field (`"draft"`, `"published"`, `"archived"`) and a numeric
`version` field.

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "doc_id": "contract-template-a",
    "version": 3,
    "status": "published"
  }
}
```

**Search only published documents:**
```json
{ "filter": { "tenant": "acme", "status": "published" } }
```

**Retrieve a specific version:**
```json
{ "filter": { "tenant": "acme", "doc_id": "contract-template-a", "version": 3 } }
```

When a new version is ingested, update older versions to `"status": "archived"` via
`document_update` so they are excluded from default published searches.

### 5.7 Content type and language

Scope search to a specific content type or locale.

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "content_type": "faq",
    "language": "en"
  }
}
```

**Search only English FAQs:**
```json
{ "filter": { "tenant": "acme", "content_type": "faq", "language": "en" } }
```

### 5.8 Time-based filtering

Store a numeric timestamp or period identifier for date-range queries.

**Ingest:**
```json
{
  "filter": {
    "tenant": "acme",
    "published_ts": 1735689600,
    "fiscal_quarter": "2025-Q4"
  }
}
```

**Search documents published after a given date:**
```json
{
  "filter": {
    "$and": [
      { "tenant": "acme" },
      { "published_ts": { "$gte": 1735689600 } }
    ]
  }
}
```

## 6. Combining filter criteria

Any of the above use cases can be combined with `$and` and `$or`. A realistic
production filter for a multi-tenant SaaS with RBAC, project scoping, and status
control:

```json
{
  "filter": {
    "$and": [
      { "tenant": "acme" },
      { "project": "proj-123" },
      { "status": "published" },
      {
        "$or": [
          { "roles": { "$in": ["admin"] } },
          {
            "$and": [
              { "roles": { "$in": ["editor"] } },
              { "security_level": { "$lte": 2 } }
            ]
          }
        ]
      }
    ]
  }
}
```

## 7. Designing filter schemas

Because filter fields are a schema decision that affects every search query, plan
them carefully before ingesting documents at scale.

**Start with the queries you need to run.** Work backwards from "what searches will
my application make?" to "what filter fields do I need on each document?" Add fields
only for dimensions you will actually filter on.

**Use stable identifiers for organizational concepts.** Use IDs (`"proj-abc"`) rather
than display names (`"My Project"`) as filter values — display names change; IDs do
not.

**Separate access control fields from organizational fields.** Keep `tenant`, `roles`,
and `security_level` clearly distinct from `project`, `folder`, and `department`.
Access control fields should always be included in every search filter; organizational
fields are optional depending on what the user is querying.

**Always include the tenant field in every search.** If your application is
multi-tenant, the tenant filter is a security boundary. Omitting it from a search
filter would expose all tenants' content in results.

**Test filter coverage before going to production.** After ingesting a representative
set of documents, run searches with your expected filter expressions and verify that
the right documents are included and excluded.
