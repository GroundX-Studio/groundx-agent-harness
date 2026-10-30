# File access through MCP

Use MCP to set file permissions, request upload URLs and create temporary links.
File bytes do not pass through MCP. The host downloads or uploads them over HTTP.

## Discover the operations

Authenticate as described in `04-auth.md`. Call `groundx_account_context`, then
`list_operations`. Before using an operation, call `describe_operation` with its
`operationId`. Check the connected server's fields; source code alone does not
mean a feature is deployed. `document_uploadlocal` in `05-workflows.md` uses the
same bucket upload service when a bucket ID is supplied.

Pass the examples below to `call_operation`. Path and body fields go in `args`;
keep document arrays and asset selectors nested. Do not add a `body` wrapper.
Never put credentials in `args`. An MCP OAuth token cannot authenticate file reads.

| Operation | Required scope |
| --- | --- |
| `Customer_get`, `Bucket_get` | `groundx:read` |
| `Customer_update`, `Bucket_create`, `Bucket_update`, `Buckets_fileUpload` | `groundx:write` |
| `Document_ingestRemote`, `Document_update`, `Document_get`, `Documents_fileLink`, `Document_retryFailedStage` | `groundx:ingest` |
| `Search_content`, `Search_documents` | `groundx:write` |
| `APIKey_list`, `APIKey_update`, `APIKey_delete` | `groundx:admin` |

A read-only session cannot set policies, upload, share or search. API-key creation
is not available through MCP, including discovery; use the dashboard or REST.

For a Partner/admin session, add `customerUsername` beside `operationId`, not in
`args`. This also requires `groundx:partner`. Keep the same customer on all calls:

```json
{"operationId":"Customer_get","customerUsername":"CUSTOMER_USERNAME","args":{}}
```

Customer sessions cannot select another customer. Use delegation only when the
connected server describes this field. Existing Partner provisioning tools keep
their own account and scope rules.

## Set a policy

Set an account default:

```json
{"operationId":"Customer_update","args":{"fileAccess":{"mode":"protected","urlTtlSeconds":300}}}
```

Create a protected bucket:

```json
{"operationId":"Bucket_create","args":{"name":"contracts","fileAccess":{"mode":"protected"}}}
```

For an existing bucket, use `Bucket_update` with its `bucketId` and `fileAccess`.
For a document, use `Document_update` with
`documents: [{documentId, fileAccess}]`. Change one document's policy at a time,
without metadata, rename or callback changes. No revision field is required.
Read the account, bucket or document afterward to confirm the result.

`mode` can be `public` or `protected`. `urlTtlSeconds` is the maximum temporary-link
lifetime, from 1 to 604800 seconds. Supply either field or both; empty objects and
null fields inside a policy are invalid. Defaults are public access and 300 seconds.

For each setting, use the document value first, then bucket, then account. A public
document can override a protected bucket. A child can set a longer link lifetime.
Omitted fields use the next available value. Saved file URLs do not expire.

On creation, omitted/null policy uses parent settings. On update, omission changes
nothing, null removes that resource's settings, and an object replaces them:

```json
{"operationId":"Bucket_update","args":{"bucketId":1234,"fileAccess":null}}
```

Use `Customer_update` with `fileAccess: null` to clear account settings.
Use `Document_update` with `documents: [{documentId, fileAccess: null}]` to clear
one document. Removing settings can make a file public; read back before reporting
success. Existing-ID ingest/retry does not change a saved policy.

## Upload a file

Request upload instructions before sending bytes, including when a protected file
belongs to a public bucket:

```json
{"operationId":"Buckets_fileUpload","args":{"bucketId":1234,"fileName":"contract.pdf","fileType":"pdf","fileAccess":{"mode":"protected"}}}
```

The **201** reply contains `{uploadId, uploadUrl, hostedUrl, expiresAt, method, headers}`.
The host PUTs the local file to `uploadUrl` with exactly the returned headers.
Do not send GroundX credentials to storage. A host limited to MCP calls needs a
file-capable host or an application upload route; no binary MCP tool exists.

Then submit the returned `hostedUrl`:

```json
{"operationId":"Document_ingestRemote","args":{"documents":[{"bucketId":1234,"sourceUrl":"RETURNED_HOSTED_URL","fileType":"pdf","fileAccess":{"mode":"protected"}}]}}
```

Use the same account, bucket and file policy for both calls. Poll
`document_getprocessingstatusbyid` and check each document's result. Reserve and
upload each file separately. Preserve its policy through batching, splits and
crawl expansion; website entries also accept initial `fileAccess`.

Finish PUT before `expiresAt`, at most 900 seconds after issuance. Protected
uploads must also be submitted for ingest before expiry; processing can finish
later. Public uploads remain ingestible after their PUT link expires. If a
protected upload expires, request another link and upload again. Never retry
through a public or hosted broker. Both public and protected uploads use this
deployment's configured API and storage, including on-prem.

## Share a file or page

```json
{"operationId":"Documents_fileLink","args":{"documentId":"DOCUMENT_ID","asset":{"kind":"page","pageNumber":2},"expiresInSeconds":60,"requireAuthentication":true}}
```

The **200** reply is `{url, expiresAt}`. Set `requireAuthentication` to true when the
recipient must use current credentials for the owning GroundX account. False
allows anyone with the link to read it. Omit the field for existing storage-signed
sharing, which also needs no GroundX key. Both explicit choices enforce expiry:
a valid key cannot rescue an expired link. Other URLs and the stored file are
unaffected. The requested lifetime cannot exceed the policy's maximum.

The caller must own the saved file. Select `source`, `xray` or `extract` by kind.
Select a `page` with its one-based `pageNumber` and optional `corrected` flag.
Select a `crop` with either `chunkId` or one-based `pageNumber` plus zero-based
`chunkIndex`. Do not supply arbitrary URLs or object keys. Raw X-Ray sharing
covers its JSON only, not the referenced files.

Keep authenticated downloads on a backend with `X-API-Key` and, for delegation,
`X-Customer-Key`. Never put keys in URLs, browser code or tool arguments. Use only
configured HTTPS GroundX hosts, without redirects. A browser address bar or image
tag cannot add these headers; use a backend or an anonymous temporary link.

Explicit true/false links need compatible API/file-service builds and an operator
signing key. Rotating that key cancels those links. Existing storage-signed links
keep working until expiry despite API-key revocation or policy changes. Verify
server support before using the new field.

## Refresh and handle errors

When a search citation expires, repeat the search or request a new link using the
saved document/page/chunk IDs. Fetch `xrayUrl` again to refresh a review view. An
owner-authenticated X-Ray GET with `?view=links` returns fresh links, rejects ranges
and leaves stored JSON unchanged. Keep raw X-Ray/extract bytes when exact content
matters. Do not make files public or retry expired URLs indefinitely.

For 400, fix the request. For 401/403, check auth, scope, selected customer and
ownership. For 404, check file existence and feature support. For 409, read the
reported conflict. For 503, honor `Retry-After`; do not bypass file permissions.
With protection disabled, policy writes/non-null initial policies return 403 and
file-link issuance returns 404. Upload issuance still works without a policy.

After an uncertain policy update, read the saved settings before retrying because
the write may have succeeded. `Document_retryFailedStage` retries a failed HTTP
callback from saved output/settings. Its **202** `{documentId, status:"processing"}`
means accepted, not complete; check status and delivery evidence. A 409 means it
cannot currently be retried. Do not re-ingest automatically. Historical source
repair is an operator task, not an MCP operation.
