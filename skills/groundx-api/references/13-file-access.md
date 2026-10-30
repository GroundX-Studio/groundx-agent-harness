# File access and sharing

Normal file URLs do not expire. By default, anyone with the URL can read the file.
A file policy can require an API key. A temporary link expires and can either
require a key or allow anyone with the link to read it.

For Python examples, use the [file-access guide](https://docs.groundx.ai/documentation/fundamentals/file-access-and-sharing).
For MCP calls, use `groundx-mcp/references/07-file-access.md`.

## Credentials and availability

Choose the API base in `01-auth.md`. Use `X-API-Key` for API calls and protected
file reads. Delegated Partner calls also use `X-Customer-Key` to select the owner.
Keep credentials on the backend. Never put keys in URLs, browser code or ingest
metadata. Send them only to configured HTTPS GroundX hosts, without redirects.
An MCP OAuth token cannot authenticate a file download.

Check that the server supports an operation and that the installed SDK exposes
its fields. Installing an SDK does not enable protection on the server. The
`public_read` storage setting controls new MinIO bucket setup, not customer
permissions; see `groundx-on-prem/references/file-access.md`.

## Policy settings and precedence

`fileAccess` accepts one or both of:

| Field | Meaning | Default |
| --- | --- | --- |
| `mode` | `public` allows anonymous reads; `protected` requires current owner access | `public` |
| `urlTtlSeconds` | Maximum lifetime of a newly issued temporary link, from 1 to 604800 seconds | 300 |

For each field, use the first value set on the document, then the bucket, then the
account. If none is set, use the default. A document can be public even when its
bucket is protected. A child setting can allow a longer link lifetime.

For example, a bucket setting only `urlTtlSeconds: 60` still uses the account's
public/protected setting. Neither policy field makes saved file URLs expire.

On creation, omitted or null `fileAccess` uses the parent settings. On update,
omission makes no change, null removes this resource's settings, and an object
replaces them. An empty object or null field inside an object is invalid.
Read `fileAccess` for the saved settings and `effectiveFileAccess` for the result.
Send the desired settings directly; no revision is required.

| Task | API operation |
| --- | --- |
| Account default | `PUT /v1/customer` with `fileAccess` |
| New bucket | `POST /v1/bucket` with `name` and optional `fileAccess` |
| Existing bucket | `PUT /v1/bucket/{bucketId}` with `fileAccess` |
| New documents | `POST /v1/ingest/documents/remote`; each document has optional `fileAccess` |
| Local multipart ingest | Each file's metadata has optional `fileAccess` |
| Website crawl | Each website entry has optional `fileAccess` |
| Existing document | `PUT /v1/ingest/documents`; one document with `documentId` and `fileAccess` |

Set protection before uploading bytes. Do not create a public file and protect it
later. Preserve initial settings through batching, splitting and crawl expansion.
Existing-ID ingest/retry keeps the saved policy; change it through the update API.
Do not combine a document policy update with metadata, rename or callback changes.
Read the saved/effective settings after an update before reporting success.

Example account or bucket update body:

```json
{"fileAccess":{"mode":"protected","urlTtlSeconds":300}}
```

Example removal of a document's settings:

```json
{"documents":[{"documentId":"DOCUMENT_ID","fileAccess":null}]}
```

## Temporary sharing

The owner calls `POST /v1/ingest/document/{documentId}/file-link`:

```json
{
  "asset":{"kind":"source"},
  "expiresInSeconds":60,
  "requireAuthentication":true
}
```

A `200` response contains `{url, expiresAt}`. Use the URL unchanged.

| `requireAuthentication` | How the recipient reads the link |
| --- | --- |
| `true` | Supply current credentials for the owning account |
| `false` | No key needed |
| Omitted | Existing storage-signed sharing, with no GroundX key needed |

Explicit true/false links use the same signature and expiry checks. An expired
link fails even with a valid key. Expiry affects that URL only; it does not delete
the file or change its other URLs. A download already streaming may finish.

The link's authentication choice applies even if the saved file policy is
different. Requested lifetime must be at least 1 second and cannot exceed the
policy's maximum. Leaving it out uses that maximum. Storage credentials can
shorten older storage-signed links.

An anonymous recipient can forward the link until it expires. Revoking an API key
or changing policy does not revoke an existing storage-signed link. Authenticated
gateway links check current owner access on every request. A raw X-Ray link shares
only its JSON, not the files referenced inside it or a `view=links` presentation.

Explicit true/false requires a signing key configured on the API and file service.
Missing configuration returns 404 and leaves older links working. Key rotation
cancels links signed with that key. Verify support before using the SDK's optional
`require_authentication` argument.

## Saved-file selectors

The service finds a saved file owned by the account; it does not sign arbitrary
URLs or object keys.

| File | `asset` |
| --- | --- |
| Original | `{"kind":"source"}` |
| Raw X-Ray | `{"kind":"xray"}` |
| Extraction output | `{"kind":"extract"}` |
| Page | `{"kind":"page","pageNumber":2,"corrected":false}` |
| Crop by chunk ID | `{"kind":"crop","chunkId":"SAVED_CHUNK_ID"}` |
| Crop by position | `{"kind":"crop","pageNumber":2,"chunkIndex":0}` |

Page numbers start at 1; chunk indices start at 0 within a saved page. Identify a
crop by chunk ID or page/index, not both.

## Upload local files

The Python `client.ingest()` helper handles upload and submission. Use the same
configured API for public and protected files, including on-prem. Do not choose
another signer based on policy or fall back to a hosted upload broker.

For an explicit upload:

1. Call `POST /v1/bucket/{bucketId}/file-upload` with `fileName`, `fileType` and any
   requested per-file `fileAccess`. Omit/null uses the parent settings. The API
   checks protection before returning upload permission.
2. Read the **201** response: `{uploadId, uploadUrl, hostedUrl, expiresAt, method, headers}`.
3. PUT the file to `uploadUrl` with exactly the returned storage headers, before
   `expiresAt`. Never send GroundX keys to storage. Browser PUTs require storage CORS.
4. Submit `hostedUrl` through remote ingest with the same owner, bucket and file
   policy. Poll the process and check individual document status.

The upload link lasts at most 900 seconds. Protected uploads must also be submitted
before it expires. Accepted submission removes that deadline from later processing.
Public uploads remain ingestible after their PUT link expires. If protected upload
expires before submission, request a new link and upload again. SDK batch helpers
stop before submitting an expired protected upload; retry a smaller batch.

`effectiveFileAccess` in the upload reply records the policy used for that upload.
Only an explicit `public` value lets clients skip protected-upload deadline checks.
Older replies without it keep those checks. This field does not grant read access.

MCP sends the upload instructions as JSON; file bytes go directly from the host to
storage. The host needs local-file and HTTP PUT access. No binary MCP tool exists.

## Read, share and refresh saved assets

Saved public URLs need no key and have no expiry. Saved protected URLs need current
owner credentials on every request and also have no expiry. GET, HEAD, ranges and
conditional requests check access before returning content. Use HTTPS even when a
stored legacy URL says HTTP; never send a key and rely on an HTTP redirect.

Browser address bars, image tags and PDF viewers cannot add GroundX headers. Use a
backend to read protected files, or issue an anonymous temporary link. Do not log
sharing URLs or send keys to native storage.

Remote ingest can read an anonymous temporary link before expiry. It cannot add
a recipient's key for an authenticated link. For that case, download the bytes on
an authorized backend and use normal upload. Denied or expired links must not get
a retry through privileged storage access.

Search citations may contain temporary source/page/crop links. Keep document,
page and chunk IDs; request another exact `file-link` or repeat the authorized
search when one expires. Refresh once, then report remaining access or file errors.
Do not make a file public to fix an expired link.

X-Ray GET `?view=links` returns fresh links for saved owned files. It needs owner
authentication even for public files, rejects ranges and leaves stored JSON
unchanged. Keep the raw X-Ray/extract when exact bytes matter; the refreshed view
is not a replacement for raw evidence.

## Errors

| Status | Action |
| --- | --- |
| 400 | Fix the policy, selector or lifetime. |
| 401 / 403 | Check credentials, selected customer, scope and ownership. Do not retry anonymously. |
| 404 | Check file ownership/existence and feature availability. |
| 409 | Read the reported conflict before resubmitting. |
| 503 | Honor `Retry-After`. Do not bypass protection while dependencies are unavailable. |

With protection disabled, policy writes and non-null initial policies return 403;
file-link issuance returns 404. Upload issuance still works without a policy.
After a lost policy-update response, read the settings before retrying because the
write may have succeeded. Failed writes do not need a background recovery process.

`POST /v1/ingest/document/{documentId}/retry` retries a failed HTTP callback from
saved output/settings. **202** `{documentId, status:"processing"}` accepts the job;
check status and delivery evidence before claiming completion. A 409 means the
current state cannot be retried. Do not re-ingest automatically. Historical source
repair is an operator procedure, not a customer or MCP operation.
