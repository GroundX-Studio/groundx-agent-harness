# File access, private uploads and sharing

Use this reference before changing file policies, uploading protected files, sharing
saved assets, or displaying source URLs. Operation-family references retain the ordinary
ingest, search, bucket and account contracts.

## Availability and authentication

These are source-defined contracts. A source branch, generated client or passing offline
test does not establish a released SDK, enabled hosted service, local MCP build or working
storage backend. Confirm the target deployment supports each operation before writing
files or changing policies. Check the installed SDK's actual methods and models before
using them; use REST for new fields until the required SDK release is verified.

REST uses `X-API-Key` on the selected API base from `01-auth.md`. Delegated Partner REST
also uses `X-Customer-Key` for the selected customer; the Partner key identifies the actor
and membership/ownership checks still apply. Never place either credential in a URL.
MCP OAuth authenticates MCP calls; its bearer token is not a file-host credential. For
standalone MCP steps, use `groundx-mcp/references/07-file-access.md`.

## Policy and inheritance

`fileAccess` is a partial override with `mode: "public" | "protected"` and/or
`urlTtlSeconds: 1..604800`. An empty object and null nested fields are invalid.
Resolution runs account, bucket, then file. A protected ancestor cannot be reopened;
a descendant cannot raise an ancestor's share-lifetime ceiling. An inherited default
without a restrictive override is public with a 300 second share lifetime. Stable
public URLs do not expire just because a share lifetime is configured.

Read `fileAccess`, `fileAccessRevision` and `effectiveFileAccess` from customer, bucket
or document readback. `fileAccess: null` means no local override. The effective value is
the confirmed inherited result, not another override to copy into every child.

| Action | Request | Revision |
| --- | --- | --- |
| Create bucket | `POST /v1/bucket`, `{ "name": "contracts", "fileAccess": { "mode": "protected" } }` | No prior revision |
| Ingest remote/local file | Each document or local metadata entry carries its own optional `fileAccess` | No prior revision for a new file |
| Crawl website | Each website entry carries optional `fileAccess`; generated documents inherit that requested override | No prior revision for new files |
| Change account default | `PUT /v1/customer`, `{ "fileAccess": { "mode": "protected" }, "fileAccessRevision": 0 }` | Use current confirmed revision, including zero |
| Change bucket override | `PUT /v1/bucket/{bucketId}`, same policy/revision fields; omit rename fields on policy-only writes | Current bucket revision |
| Change file override | `PUT /v1/ingest/documents`, `{ "documents": [{ "documentId": "DOCUMENT_ID", "fileAccess": null, "fileAccessRevision": 0 }] }` | Current file revision |

On creation, omitted or null `fileAccess` inherits. For an existing resource, omission
leaves the override unchanged; explicit null plus the current revision clears it. A
policy replacement is not a merge of its previous fields. Policy updates permit one document per request and cannot be mixed with ordinary metadata
or callback changes. Existing-ID ingest/retry does
not become an unrevisioned policy-update shortcut. Read back the confirmed policy before
reporting success. Do not implement protected creation as create-public then update.

Two different initial file overrides belong inside the existing document envelope:

```json
{
  "documents": [
    { "bucketId": 1234, "sourceUrl": "PRIVATE_HOSTED_URL_A", "fileAccess": { "mode": "protected", "urlTtlSeconds": 60 } },
    { "bucketId": 1234, "sourceUrl": "PRIVATE_HOSTED_URL_B", "fileAccess": { "mode": "protected", "urlTtlSeconds": 120 } }
  ]
}
```

Preserve each override through bulk/directory batching, Office/PDF preparation, CSV
splitting and crawl expansion. A public override is valid only where ancestors permit it.

## Local-file upload flow

Use the same authenticated bucket endpoint for public and protected files. It remains
available when file protection is disabled. The configured GroundX API signs against
its own storage, including local S3-compatible deployments. Clients do not choose a
different signer based on policy or fall back to the hosted broker. Protected files
remain private from their first byte, including protected files in public buckets.

1. `POST /v1/bucket/{bucketId}/file-upload` with
   `{ "fileName": "contract.pdf", "fileType": "pdf" }` for public inheritance.
   Include `"fileAccess": {"mode":"protected"}` for a requested protected file,
   and send that same override during ingest. A disabled deployment rejects a
   non-null policy with 403 before any native PUT grant is returned.
2. Accept **201** with `{ uploadId, uploadUrl, hostedUrl, expiresAt, method, headers }`.
   `method` is `PUT`; the grant lasts at most 900 seconds and can be shorter.
3. PUT the file bytes to `uploadUrl` using the returned `headers`. Send no GroundX
   credential to native storage. Browsers require storage CORS for this direct PUT.
4. Submit `hostedUrl` through the existing remote-ingest `documents` envelope with the
   selected `bucketId` and requested per-file `fileAccess`, then poll the returned process.

The optional `effectiveFileAccess` records the policy used for issuance. Explicit
public mode has no ingest deadline from PUT expiry; missing metadata retains
existing conservative protected-upload checks. It does not grant read permission
or confirm the current policy.

Complete PUT before `expiresAt`. Private reservations also require ingest submission
before that deadline; accepted ingest binds the reservation, so later processing is
not limited to the upload window. Only effective-protected uploads create a private
reservation. Public sources remain ingestible after PUT expiry, even when the
file-protection feature is enabled.
SDK helpers stop before ingest submission if a batch's private reservation has
expired. Retry with fewer files; uploads are not automatically renewed.
Keep the same customer and bucket throughout. An expired upload grant requires a fresh
reservation and upload; do not substitute the public broker. HTTP/MCP API calls carry
JSON control data only; file bytes travel directly to storage. The host must be able to
read the local file and issue the PUT. Released `client.ingest()` helpers can be used for
protected local files only after their private-staging and initial-policy support is
verified. Until then, use this explicit REST flow rather than inventing SDK methods.

## Read, share and refresh saved assets

Stable protected source/page/crop/X-Ray/extract URLs use current `X-API-Key` authentication
on every gateway read, with `X-Customer-Key` for delegated Partner access. Keep keys on
the backend. Upgrade legacy HTTP links to HTTPS before adding credentials; do not
send authenticated HTTP requests or rely on redirects. A browser image tag, PDF viewer or address bar cannot add these headers;
use an authenticated application proxy or a short-lived native link.

`POST /v1/ingest/document/{documentId}/file-link` accepts a saved asset selector and
optional `expiresInSeconds` (1..604800, bounded by effective policy and storage credentials):

```json
{ "asset": { "kind": "page", "pageNumber": 2, "corrected": false }, "expiresInSeconds": 60 }
```

Selectors are `source`, `xray`, `extract`; `page` with one-based `pageNumber` and optional
`corrected`; or `crop` with `chunkId`, or one-based `pageNumber` plus zero-based
`chunkIndex`. The service resolves an owned saved asset. It does not sign arbitrary
caller-supplied URLs. A 200 response contains `{ url, expiresAt }`.

The native URL is a reusable, forwardable bearer grant until `expiresAt`. Revoking a
GroundX key or changing policy does not revoke an already issued native grant. Keep
lifetimes short, do not log URLs, and never append keys to them. Stable public links
remain usable anonymously where policy permits.

Search source/citation links may be temporary native grants. Retain document/page/chunk
identity so an expired view can refresh through an authenticated search or an exact
`file-link` request. Refresh once and surface authorization or missing-asset errors;
never repair expiry by making files public or retrying the same expired URL forever.

Raw X-Ray and raw extract remain evidence. An authenticated X-Ray gateway GET with
`?view=links` returns a presentation copy with refreshed links for verified saved owned
assets. It requires API-key auth even when raw files are public, does not accept Range,
and does not rewrite stored bytes or sign external URLs. Do not save that presentation
as immutable raw evidence or replace certified fixtures with it.

## Failures and retry

| Status | Response |
| --- | --- |
| 400 | Fix policy, selector or lifetime. No empty policy object or null nested field. |
| 401 / 403 | Resolve credentials, selected customer, scope or ownership. A disabled deployment also rejects policy writes and non-null initial policies with 403. Do not blind-retry. |
| 404 | Check the saved document/asset exists for this owner. File-link returns 404 when file access is disabled; upload issuance remains available. |
| 409 | Reread revision/ownership state and reconsider the mutation before resubmitting. |
| 503 | Honor `Retry-After`; protection remains fail-closed while trustworthy state is unavailable. |

Policy updates commit in one transaction. A precommit failure keeps the previous
settings and revision. After a timeout or lost response, read the current settings
before retrying: commit may have succeeded, and the old revision then returns 409.
There is no pending-policy workflow or background recovery.

`POST /v1/ingest/document/{documentId}/retry` retries the currently failed HTTP delivery callback using saved output and callback settings. **202** returns `{ "documentId": "DOCUMENT_ID", "status": "processing" }`;
acceptance is not completion. Reread document status and delivery evidence. A 409 means
the current state is not eligible; do not automatically re-ingest or repeat the retry.
Historical source repair is an operator procedure, not a customer API or MCP operation.
