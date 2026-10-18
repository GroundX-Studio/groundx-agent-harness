# File policies, private upload and saved-asset sharing over MCP

This workflow is standalone. Confirm the connected server exposes the operations and
schemas below before using them. Source support and offline tests do not prove hosted
rollout, released SDK support or a working on-prem storage backend. The `document_uploadlocal`
flow in `05-workflows.md` uses the same bucket issuer when bucketId is supplied.

## Discover and authenticate

Configure OAuth or the `X-API-Key` MCP transport header using `04-auth.md`. Never pass
credentials in `args`. OAuth tokens for MCP are not file-host credentials. Start with:

```json
groundx_account_context({})
list_operations({})
describe_operation({ "operationId": "Customer_get" })
describe_operation({ "operationId": "Customer_update" })
```

Describe every non-default operation before calling it. Path, query and JSON-body fields
are flattened into `args`; keep nested document arrays and asset selectors intact.
Do not wrap a flattened body in a new `body` or `request` field.

| Operation | Scope |
| --- | --- |
| `Customer_get`, `Bucket_get` | `groundx:read` |
| `Customer_update`, `Bucket_create`, `Bucket_update`, `Buckets_fileUpload` | `groundx:write` |
| `Document_ingestRemote`, `Document_update`, `Document_get`, `Documents_fileLink`, `Document_retryFailedStage` | `groundx:ingest` |
| `Search_content`, `Search_documents` | `groundx:write` |
| `APIKey_list`, `APIKey_update`, `APIKey_delete` | `groundx:admin` |

A read-only session cannot change policy, reserve uploads, share files or search. The
`/ingest` scope rule includes file-link issuance. Customer API-key creation is excluded from MCP,
including discovery, regardless of scope; use the dashboard or authorized REST path.

## Delegated customer selection

A compatible Partner/admin session adds top-level `customerUsername` beside
`operationId` and `args`, not inside `args`. This requires `groundx:partner` plus the
normal operation scope. The server maps it to `X-Customer-Key`; backend membership and
ownership checks remain authoritative. Customer sessions reject this selector. For
example, after describing the operation:

```json
call_operation({ "operationId": "Customer_get", "customerUsername": "CUSTOMER_USERNAME", "args": {} })
```

Keep that selected customer on policy, reservation, ingest, sharing and refresh calls.
A server that omits this field does not establish delegated support. This extension is
source-defined in MCP 0.1.2; verify the connected deployment before use. Separate named
Partner resource/provisioning tools retain their own account-mode and scope rules.

## Protect an account or create a protected bucket

Read the current account policy/revision, then use its actual confirmed revision:

```json
call_operation({ "operationId": "Customer_get", "args": {} })
call_operation({ "operationId": "Customer_update", "args": { "fileAccess": { "mode": "protected", "urlTtlSeconds": 300 }, "fileAccessRevision": 0 } })
```

Zero is a valid revision. Read back after the write. For a new bucket, describe
`Bucket_create`, then create with initial policy in the same request:

```json
call_operation({ "operationId": "Bucket_create", "args": { "name": "contracts", "fileAccess": { "mode": "protected" } } })
```

Creation has no previous revision. Omitted or null initial `fileAccess` inherits.
Policy resolution is account, bucket, file. A protected ancestor cannot be reopened;
share lifetimes cannot exceed ancestor ceilings. `fileAccess` may contain `mode`,
`urlTtlSeconds` (1..604800), or both; an empty object or null nested value is invalid.

Document policy changes permit one document and no ordinary metadata/callback changes
in the same request. For existing buckets/files, use the current confirmed revision on every policy write.
Omitted `fileAccess` leaves the override unchanged; explicit null clears it and inherits:

```json
call_operation({ "operationId": "Bucket_update", "args": { "bucketId": 1234, "fileAccess": null, "fileAccessRevision": 0 } })
call_operation({ "operationId": "Document_update", "args": { "documents": [{ "documentId": "DOCUMENT_ID", "fileAccess": null, "fileAccessRevision": 0 }] } })
```

Describe those operations first. A 409 requires fresh readback and a new decision; do
not blindly replace the revision. A policy replacement does not merge previous fields.

## Upload local files before ingest

Use the same bucket upload endpoint for public and protected files, including when
read protection is disabled. It signs against this deployment's configured storage,
without a hosted broker fallback. Describe and call:

```json
describe_operation({ "operationId": "Buckets_fileUpload" })
call_operation({ "operationId": "Buckets_fileUpload", "args": { "bucketId": 1234, "fileName": "contract.pdf", "fileType": "pdf", "fileAccess": { "mode": "protected" } } })
```

Include the requested per-file policy in upload issuance and ingest. Omit it or use
null for inheritance. The API validates it before returning any grant; disabled
protection rejects non-null policies with 403 before bytes can be sent.

The API returns **201** JSON `{ uploadId, uploadUrl, hostedUrl, expiresAt, method, headers }`.
The MCP host reads the local file and PUTs its bytes to `uploadUrl` using `method` and
`headers`. Send no GroundX credential to native storage. The upload grant lasts at most
900 seconds. Complete PUT before `expiresAt`. For private reservations, also submit
ingest before expiry; accepted ingest binds the reservation, so later processing is
not limited to that window. Unreserved public sources remain ingestible after PUT
expiry. A host limited to MCP tool calls cannot transfer local bytes; it needs a
file-capable host or an authenticated application upload path. No binary MCP tool exists.

After PUT succeeds, describe `Document_ingestRemote` and submit the existing envelope:

```json
call_operation({ "operationId": "Document_ingestRemote", "args": { "documents": [
  { "bucketId": 1234, "sourceUrl": "PRIVATE_HOSTED_URL_A", "fileAccess": { "mode": "protected", "urlTtlSeconds": 60 } },
  { "bucketId": 1234, "sourceUrl": "PRIVATE_HOSTED_URL_B", "fileAccess": { "mode": "protected", "urlTtlSeconds": 120 } }
] } })
```

Reserve and upload each file separately. Carry per-file overrides through prepared/split
files, bulk batches and directory helpers; crawl entries similarly carry an initial
policy to their generated documents. Omitted/null initial policy inherits. Never upload
to the public broker then change policy. An expired PUT needs a fresh private reservation.
Keep the same owner/bucket and poll `document_getprocessingstatusbyid` until complete.
Existing-ID retries are not a bypass of revisioned policy updates.

## Share a page and refresh citations

```json
describe_operation({ "operationId": "Documents_fileLink" })
call_operation({ "operationId": "Documents_fileLink", "args": { "documentId": "DOCUMENT_ID", "asset": { "kind": "page", "pageNumber": 2 }, "expiresInSeconds": 60 } })
```

The **200** JSON response is `{ url, expiresAt }`. `asset` can select `source`, `xray`,
`extract`; `page` with one-based `pageNumber` and optional `corrected`; or `crop` with
`chunkId`, or `pageNumber` plus zero-based `chunkIndex`. The service resolves saved owned
assets, not arbitrary URLs. Requested lifetime is bounded by effective policy and
storage credentials. Anyone holding a native link can reuse/forward it until expiry;
policy changes or key revocation do not revoke an existing grant. Do not log signed URLs.

Stable protected file URLs need current API-key header auth on the file gateway.
Upgrade legacy HTTP links to HTTPS before adding credentials, without an authenticated
HTTP redirect. Browser image tags, PDF viewers and address bars cannot add those headers; use a
backend authenticated proxy or the short-lived native link. Do not send MCP OAuth
tokens to storage or put keys in URLs. Public stable URLs remain anonymous where allowed.

For expired search citations, repeat the authenticated search or issue an exact
`Documents_fileLink` using saved document/page/chunk identity, then update the view.
Do not keep retrying an expired URL or change policy. Raw X-Ray/extract bytes remain
immutable evidence. API-key-authenticated X-Ray GET `?view=links` produces a presentation
copy with refreshed owned links, requires auth even for public files, rejects Range and
does not modify stored raw content. Its output is not a raw fixture replacement.

## Retry and failures

```json
describe_operation({ "operationId": "Document_retryFailedStage" })
call_operation({ "operationId": "Document_retryFailedStage", "args": { "documentId": "DOCUMENT_ID" } })
```

**202** `{ documentId, status: "processing" }` accepts a retry of the currently failed HTTP callback using saved output and callback settings;
reread document status and delivery evidence before reporting completion. A 409 means
state is not eligible and does not authorize re-ingest.

For 400, fix schema/selector/lifetime. For 401/403, fix auth, scope, selected customer or
ownership. A disabled deployment rejects policy writes and non-null initial policies
with 403, and file-link operations with 404. Upload issuance remains available. These are not retryable
outages. Otherwise, for 404, verify the saved asset exists. For 409, reread confirmed state.
For 503, honor `Retry-After`; fail-closed protection is not a reason to use public storage.
Keep all JSON response shapes, including 201/202; no response implies file bytes passed
through MCP. Historical repair is operator-only.
