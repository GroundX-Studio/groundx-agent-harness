# Advanced Operation Discovery

Use this reference when calling an operation that is not in the default 12 tool set. The
three always-present meta-tools (`list_operations`, `describe_operation`, `call_operation`)
make advanced GroundX operations exposed by `list_operations` reachable from an MCP session,
subject to scope and explicit server denylist rules.

---

## 1. When discovery is needed

The default 12 tools cover the common ingest-to-search workflow (bucket creation, group
management, document ingestion, polling, and search). Operations outside that set — bucket
deletion, document deletion, workflow management, existing API key management, and other
administrative or destructive operations — are not registered as named MCP tools. Exposed
advanced operations are reachable only through the discovery path documented in this file.

Use discovery when:

- The operation you need is not in the default 12 (see `references/02-default-tools.md` for
  the full list).
- You need to confirm the exact parameter schema for an operation before calling it.
- The user names an operation that does not appear in the default tool list.

For the default 12 and the 4 always-present tools, their parameter schemas are already
documented in `references/02-default-tools.md` — no describe step is needed before calling
them.

---

## 2. Step 1 — List available operations

`list_operations({})` returns the GroundX API operations exposed through the MCP discovery
path for the current server build. Each entry contains enough information to identify the
operation and decide whether it matches the task.

**Tool call:**

```json
list_operations({})
```

**Example response:**

```json
{
  "endpoints": [
    {
      "operationId": "Bucket_delete",
      "method": "DELETE",
      "path": "/v1/bucket/{bucketId}",
      "summary": "Delete a bucket",
      "description": "Permanently deletes a bucket and all documents it contains."
    },
    {
      "operationId": "Document_delete1",
      "method": "DELETE",
      "path": "/v1/ingest/document/{documentId}",
      "summary": "Delete a document",
      "description": "Removes a document from the ingest pipeline and all associated buckets."
    },
    {
      "operationId": "APIKey_list",
      "method": "GET",
      "path": "/v1/apikey",
      "summary": "List API keys",
      "description": "Returns all API keys associated with the current account."
    }
  ]
}
```

Identify the `operationId` of the operation you want. Use that exact string in Step 2.
If an operation is not returned by `list_operations`, do not assume it is callable through
`call_operation` — some operations are intentionally unavailable through MCP even for
admin-scoped sessions.

---

## 3. Step 2 — Describe the operation

`describe_operation({ "operationId": "<id>" })` returns the full parameter schema for a
single operation. Use this to build a valid `args` object before calling.

**Tool call:**

```json
describe_operation({ "operationId": "Bucket_delete" })
```

**Example response:**

```json
{
  "operationId": "Bucket_delete",
  "method": "DELETE",
  "path": "/v1/bucket/{bucketId}",
  "summary": "Delete a bucket",
  "description": "Permanently deletes a bucket and all documents it contains.",
  "parameters": [
    {
      "name": "bucketId",
      "in": "path",
      "required": true,
      "type": "integer"
    }
  ],
  "inputSchema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["bucketId"],
    "properties": {
      "bucketId": {
        "type": "integer"
      }
    }
  }
}
```

`parameters` lists every accepted argument with its name, location (`path`, `query`, or
`header`), whether it is required, and its type. `inputSchema` is the exact JSON schema for
the `args` object in Step 3; it flattens path, query, and JSON body fields into one
argument object.

---

## 4. Step 3 — Call the operation

`call_operation({ "operationId": "<id>", "args": { ... } })` executes the operation and
returns the proxied result from the GroundX API.

**CRITICAL:** The argument key is `operationId` for both `describe_operation` and
`call_operation` — not `operation_id`. Use the exact `operationId` string returned by
`list_operations`.

**Tool call:**

```json
call_operation({
  "operationId": "Bucket_delete",
  "args": { "bucketId": 12345 }
})
```

The `args` object maps parameter names (as given in `describe_operation`) to their values.
Path parameters, query parameters, and request-body fields all go into `args` — the server
resolves placement from the operation schema.

**Example response:**

```json
{
  "status": 200,
  "body": { "message": "Bucket deleted." }
}
```

---

## 5. Scope enforcement

`operationAllowedByScopes` applies inside `call_operation` before dispatch, using the same
derived-scope rule as the default tools:

| Condition | Required scope |
|---|---|
| Operation path contains `/ingest` | `groundx:ingest` |
| Write verb (POST, PUT, PATCH, DELETE) on any other path | `groundx:write` |
| All other operations | `groundx:read` |

A session configured with only `groundx:read` cannot execute write or ingest operations
through `call_operation`. The server evaluates scope and rejects the call with a scope
error before the underlying API request is made — no partial execution occurs.

Examples:

- `Bucket_delete` (DELETE `/v1/bucket/{bucketId}`) requires `groundx:write`. A read-only
  session receives a scope error.
- `Document_delete1` (DELETE `/v1/ingest/document/{documentId}`) requires `groundx:ingest`
  (path contains `/ingest`). A session with only `groundx:write` also receives a scope error.

### 5.1 Sensitive operations

A few operations are not governed by the verb rule above:

- **Credential / account-administration operations require `groundx:admin`.** Managing
  existing API keys — `APIKey_list`, `APIKey_update`, `APIKey_delete` — is callable only in an
  admin-scoped session; a `groundx:write` session receives a scope error.
- **Creating API keys is not available through MCP.** `APIKey_create` is hidden from
  `list_operations` and rejected by `call_operation` regardless of scope — API keys are minted
  out of band (REST or the dashboard), never by an agent.

Discovery does not bypass scope checks; the same rules are enforced on the default 12 tools.

---

## 6. Quick reference

| Step | Tool | Key argument | Returns |
|---|---|---|---|
| 1. Browse | `list_operations` | `{}` | `{ endpoints: [{ operationId, method, path, summary, description }] }` |
| 2. Inspect | `describe_operation` | `{ "operationId": "..." }` | EndpointDetail with `parameters[]` and `inputSchema` |
| 3. Execute | `call_operation` | `{ "operationId": "...", "args": { ... } }` | Proxied API response |

Argument-name invariant: `operationId` (camelCase, no underscore) is the correct key for
both `describe_operation` and `call_operation`.

For the default 12 tools and their parameters, see `references/02-default-tools.md` — no
discovery step is required for those.
