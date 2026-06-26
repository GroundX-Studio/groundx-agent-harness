# Breaking-Change Migration: Full Tool List → 12 Default Tools

Use this reference when migrating from the old GroundX MCP server behavior that registered
the full OpenAPI tool list as direct MCP tools. Any MCP client that called advanced or
destructive operations by their old registered names must switch to the discovery path.

Do not rely on memory for tool names or `operationId` values. Verify the current 12 default
tools and 4 always-present tools in `references/02-default-tools.md`. The three-step
discovery pattern is documented in `references/03-discovery.md`.

---

## 1. Summary

The GroundX MCP server default tool list has been reduced from the full OpenAPI tool list to
exactly **12 default tools** plus **4 always-present tools**. This is a breaking change for
any MCP client that relied on the full set of directly-registered tools. Clients that used
only the 12 default tools (see `references/02-default-tools.md`) are unaffected. Clients that
called advanced or destructive operations by their old direct tool names must migrate to the
`call_operation` discovery path.

---

## 2. What Changed

### 2.1 New default surface

The default registered set now contains exactly **12 task-oriented tools** covering the most
common document workflows — ingest, status polling, document management, search, bucket/group
management, and health. Those tools are listed with their normalized names, `operationId`
values, and derived scopes in `references/02-default-tools.md`.

In addition, **4 tools are always present** regardless of session scope:
`groundx_account_context`, `list_operations`, `describe_operation`, and `call_operation`.

### 2.2 What was removed from direct registration

Advanced and destructive operations are **no longer registered as direct MCP tools**. This
includes, but is not limited to:

- `bucket_delete`
- `document_delete`
- Workflow management operations
- API key management operations
- Any other OpenAPI operation that was previously registered as a direct tool but does not
  appear in the 12-tool default set in `references/02-default-tools.md`

**Calling an old registered name now returns a tool-not-found error.** The old direct tool
names no longer resolve.

---

## 3. No Restore-Full-List Switch

There is **no configuration option, flag, or environment variable** to restore the old full
tool list. The simplified default surface is intentional and permanent (Run-2 design decision,
AGE-151). Do not document or suggest any restore path — it does not exist.

The supported path for all advanced and destructive operations is the `call_operation`
discovery pattern described in Section 4 below.

---

## 4. Migration Path

All operations that were removed from direct registration remain **reachable through the three
meta-tools** using the discovery pattern. See `references/03-discovery.md` for the full
discovery reference.

The three-step pattern:

### 4.1 Step 1 — Find the operationId

Call `list_operations({})` to retrieve the list of all available operations with their
`operationId` values.

```
list_operations({})
```

No arguments are required. Returns an array of operation descriptors each containing an
`operationId`.

### 4.2 Step 2 — Inspect the schema

Call `describe_operation` with the `operationId` found in step 1 to retrieve the full
argument schema for that operation.

```
describe_operation({ "operationId": "<id>" })
```

Note: the argument is named `operationId` (camelCase), not `operation_id`.

### 4.3 Step 3 — Execute

Call `call_operation` with the `operationId` and an `args` object matching the schema
returned in step 2.

```
call_operation({ "operationId": "<id>", "args": { ... } })
```

Note: the identifier argument is named `operationId` (camelCase) for **both**
`describe_operation` and `call_operation`. This is consistent — there is no `operation_id`
snake_case variant.

---

## 5. Before and After Example

### 5.1 Bucket delete

**Before — old direct tool (no longer works):**

```
bucket_delete({ "bucketId": 12345 })
```

This call now returns a tool-not-found error because `bucket_delete` is no longer registered
as a direct tool.

**After — via call_operation:**

```
call_operation({ "operationId": "Bucket_delete", "args": { "bucketId": 12345 } })
```

Use `list_operations({})` to confirm the exact `operationId` string if uncertain — for
example `Bucket_delete` uses title-case prefix and camelCase suffix, matching the GroundX
OpenAPI `operationId` convention.

### 5.2 Document delete

**Before — old direct tool (no longer works):**

```
document_delete1({ "documentId": "abc-123" })
```

**After — via call_operation:**

```
call_operation({ "operationId": "Document_delete1", "args": { "documentId": "abc-123" } })
```

---

## 6. Scope Enforcement — Unchanged on Both Paths

Scope enforcement is **unchanged** before and after this migration. The
`operationAllowedByScopes` rule applies before dispatch in `call_operation` using the same
derived-scope logic as the 12 default tools:

1. Path contains `/ingest` → requires `groundx:ingest`
2. Write verb (POST / PUT / PATCH / DELETE) on any other path → requires `groundx:write`
3. All other operations → requires `groundx:read`

If an advanced or destructive operation was restricted by scope before (because it required
`groundx:write` or `groundx:ingest` and the session held only `groundx:read`), it remains
restricted when called through `call_operation`. The migration path does not expand permissions.

Read-only sessions (`groundx:read` only) can call `call_operation` but will receive a scope
error for any write or ingest operation, the same as before. For the derived-scope rule and
read-only session visibility details, see `references/02-default-tools.md`.
