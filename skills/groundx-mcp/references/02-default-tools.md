# 02 — Default Tool Reference

The finalized GroundX MCP tool surface: 12 default tools, 4 always-present tools, the
derived-scope rule, and read-only session visibility. Use tool names verbatim from this file.
Do not invent, abbreviate, or guess names from memory.

---

## 1. Default Tools (12)

These tools are registered for every session. Which ones are visible in a given session
depends on the session's granted scopes — see section 3 for the scope-derivation rule and
section 4 for read-only visibility.

| normalized name | operationId | method | path | derived scope |
|---|---|---|---|---|
| `document_ingestremote` | Document_ingestRemote | POST | /v1/ingest/documents/remote | groundx:ingest |
| `document_getprocessingstatusbyid` | Document_getProcessingStatusById | GET | /v1/ingest/{processId} | groundx:ingest |
| `document_list` | Document_list | GET | /v1/ingest/documents | groundx:ingest |
| `document_get` | Document_get | GET | /v1/ingest/document/{documentId} | groundx:ingest |
| `search_content` | Search_content | POST | /v1/search/{id} | groundx:write |
| `search_documents` | Search_documents | POST | /v1/search/documents | groundx:write |
| `bucket_create` | Bucket_create | POST | /v1/bucket | groundx:write |
| `bucket_list` | Bucket_list | GET | /v1/bucket | groundx:read |
| `group_create` | Group_create | POST | /v1/group | groundx:write |
| `group_list` | Group_list | GET | /v1/group | groundx:read |
| `group_addbucket` | Group_addBucket | POST | /v1/group/{groupId}/bucket/{bucketId} | groundx:write |
| `health_get` | Health_get | GET | /v1/health/{service} | groundx:read |

Always use the **normalized lowercase_underscore** name (left column) in tool calls. The
PascalCase `operationId` column is for cross-referencing with OpenAPI and with `call_operation`
— see `references/03-discovery.md`.

---

## 2. Always-Present Tools (4)

These 4 tools are registered unconditionally, regardless of the session's granted scopes.

| tool | input | output |
|---|---|---|
| `groundx_account_context` | `{}` | AccountContext: resolved account type, mode, granted scopes, base URL, enabled tool groups |
| `list_operations` | `{}` | `{ endpoints: [{ operationId, method, path, summary, description }] }` — all exposed operations reachable via `call_operation` |
| `describe_operation` | `{ operationId }` | EndpointDetail: path, method, summary, description, operationId, parameters[], inputSchema — or error if not found |
| `call_operation` | `{ operationId, args? }` | proxied execution result; scope enforced via `operationAllowedByScopes` before dispatch |

Language note: there are **3 discovery meta-tools** (`list_operations`, `describe_operation`,
`call_operation`) **plus** the always-present `groundx_account_context` — together these are the
**4 always-present tools**. Never say "3 meta-tools" without this clarification.

Both `describe_operation` and `call_operation` use the argument name `operationId` (not
`operation_id`). This is the same name used by `pkg/model/mcp/endpoint.go` in the MCP server.

---

## 3. Derived-Scope Rule

The function `operationAllowedByScopes(path, method)` determines the minimum scope required for
an operation. It applies both when filtering visible default tools and inside `call_operation`
before dispatch:

1. If the path contains `/ingest` → required scope is `groundx:ingest`
2. Else if the method is a write verb (POST, PUT, PATCH, or DELETE) → required scope is `groundx:write`
3. Else → required scope is `groundx:read`

Note that POST search endpoints (`/v1/search/...`) fall under rule 2 and therefore require
`groundx:write`. This is intentional — search is a write-scoped operation.

There is no environment flag or opt-in to restore the old full tool list. The 12-tool default
is the only supported surface; advanced and destructive operations are reached via
`call_operation` (see `references/03-discovery.md`).

---

## 4. Read-Only Session Visibility

A session granted only `groundx:read` sees a reduced set from the 12 default tools. Only
operations whose derived scope is `groundx:read` are visible:

| tool | method | path |
|---|---|---|
| `bucket_list` | GET | /v1/bucket |
| `group_list` | GET | /v1/group |
| `health_get` | GET | /v1/health/{service} |

All ingest-scoped and write-scoped default tools — including both search tools — are not
visible in a read-only session.

The 4 always-present tools (`groundx_account_context`, `list_operations`, `describe_operation`,
`call_operation`) are present regardless of scope. However, `call_operation` still enforces
`operationAllowedByScopes` before dispatch: a read-only session cannot execute write or ingest
operations via `call_operation`.

---

## 5. Usage Notes

- Always use the normalized lowercase_underscore name (e.g., `document_ingestremote`), not the
  PascalCase operationId (e.g., `Document_ingestRemote`), when calling a default tool directly.
- Ingest is asynchronous. `document_ingestremote` returns a `processId`. Poll
  `document_getprocessingstatusbyid` until the process is complete before calling
  `search_content` or `search_documents`.
- Advanced and destructive operations — including bucket deletion, document deletion,
  workflow management, and API key management — are not in the default 12. Use
  `list_operations` to find the exact `operationId`, then reach them via `call_operation`.
  See `references/03-discovery.md` for the list → describe → call pattern.
- Never place the raw API key in any tool argument. Authentication is transport-layer only
  (`X-API-Key` header or the OAuth flow). See `references/04-auth.md`.
