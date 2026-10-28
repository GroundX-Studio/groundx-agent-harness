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

## Service storage settings

`ContainerUploadSettings.public_read` is an operator setting for extraction, not
an account, bucket or document policy. It does not change S3 permissions or update
existing MinIO bucket policies. Do not use it to protect or unprotect a customer's
files. For its default, new-bucket behavior and extraction read requirements,
read `groundx-on-prem/references/file-access.md`.

## Python quick start

These examples use GroundX Python SDK 4.1.4. Install or upgrade with
`pip install --upgrade groundx`. Confirm that your deployment supports file
protection before uploading sensitive files.

Keep the API key in your server environment. For dev or on-prem, set
`GROUNDX_BASE_URL` to that deployment's API base, including `/api`.

```python
import os
from groundx import GroundX, Document, DocumentUpdate, FileAccessPolicy

client = GroundX(
    api_key=os.environ["GROUNDX_API_KEY"],
    base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
)
policy = FileAccessPolicy(mode="protected", url_ttl_seconds=300)
```

Choose the narrowest scope you need. Account settings provide the default; bucket
and document settings override it field by field. A document can explicitly allow
public access even when its bucket or account is protected.

### Account default

```python
client.customer.update(file_access=policy)
```

### Bucket settings

Create a protected bucket:

```python
created = client.buckets.create(name="private-documents", file_access=policy)
BUCKET_ID = created.bucket.bucket_id
```

For an existing bucket, set `BUCKET_ID` to its bucket ID, then update its settings:

```python
client.buckets.update(BUCKET_ID, file_access=policy)
```

### Protect a file during upload and ingest

Set the policy before uploading, including when the destination bucket is public.
The helper requests an upload link from your configured API, uploads to storage and
submits the document with its policy.

```python
result = client.ingest(
    documents=[Document(
        bucket_id=BUCKET_ID,
        file_path="contract.pdf",
        file_access=policy,
    )],
    wait_for_complete=True,
)
```

Check individual document status before using the result. For remote files, set
`file_path` to the source URL and supply `file_name` and `file_type` on `Document`.
GroundX must be able to read that source. Protection does not secure a copy on a
third-party host.

### Change an existing file

Replace the placeholder below with an owned document ID from a document lookup
or the dashboard. A policy update contains one document and no metadata, rename
or callback changes. It does not rerun processing.

```python
DOCUMENT_ID = "your-document-id"
client.documents.update(documents=[
    DocumentUpdate(document_id=DOCUMENT_ID, file_access=policy),
])
```

On creation, an omitted policy inherits. On update, omitting `file_access` leaves
the current override unchanged; `None` clears it. A supplied policy replaces the
previous override. No revision lookup or revision argument is required. Read the
resource again to confirm its saved and effective settings:

```python
account = client.customer.get().customer
bucket = client.buckets.get(BUCKET_ID).bucket
document = client.documents.get(DOCUMENT_ID).document
```

Inspect `file_access` for the saved override and `effective_file_access` for the
settings in effect. If the document is absent, check its ID, owner and processing
status before continuing.

### Share the original file temporarily

Select the saved asset explicitly. This example shares the original document:

```python
from groundx import AssetSelectorZero

link = client.documents.file_link(
    DOCUMENT_ID,
    asset=AssetSelectorZero(kind="source"),
    expires_in_seconds=60,
)
download_url = link.url
expires_at = link.expires_at
```

`AssetSelectorZero` is the generated SDK type for stored source, X-Ray and extract
selectors. A temporary link is separate from the policy hierarchy. Anyone who has
it can download and forward it until expiry. No GroundX key is sent with that
storage request. Key revocation or a later policy change does not revoke an
already issued link. See [asset selectors below](#read-share-and-refresh-saved-assets) for pages,
crops and other stored outputs.

For a stable protected URL, use the authenticated server-side request in
[Read, share and refresh saved assets](#read-share-and-refresh-saved-assets).

### Remove an override

Run a clearing request only when you intend to remove that scope's settings.
Clearing all applicable overrides makes stable links public.

Clear the account settings and use the public system defaults:

```python
client.customer.update(file_access=None)
```

Clear a bucket's settings and inherit the account settings:

```python
client.buckets.update(BUCKET_ID, file_access=None)
```

Clear a document's settings and inherit bucket and account settings:

```python
client.documents.update(documents=[
    DocumentUpdate(document_id=DOCUMENT_ID, file_access=None),
])
```

## Policy and inheritance

`fileAccess` is a partial override with `mode: "public" | "protected"` and/or
`urlTtlSeconds: 1..604800`. An empty object and null nested fields are invalid.
For each field, use document settings first, then bucket settings, then account
settings. Omitted fields use the broader value. Explicit public mode and longer
sharing lifetimes are allowed. Defaults are public mode and a 300-second sharing
lifetime. Stable public URLs never expire. An issued temporary sharing link works
without API credentials until its storage expiry, regardless of later policy changes.

Read `fileAccess` and `effectiveFileAccess` from customer, bucket
or document readback. `fileAccess: null` means no local override. The effective value is
the confirmed inherited result, not another override to copy into every child.

| Action | Request |
| --- | --- |
| Create bucket | `POST /v1/bucket`, `{ "name": "contracts", "fileAccess": { "mode": "protected" } }` |
| Ingest remote/local file | Each document or local metadata entry carries its own optional `fileAccess` |
| Crawl website | Each website entry carries optional `fileAccess`; generated documents keep that policy |
| Change account default | `PUT /v1/customer`, `{ "fileAccess": { "mode": "protected" } }` |
| Change bucket override | `PUT /v1/bucket/{bucketId}`, same policy fields; omit rename fields |
| Change file override | `PUT /v1/ingest/documents`, `{ "documents": [{ "documentId": "DOCUMENT_ID", "fileAccess": null }] }` |

Send the desired policy directly, without fetching a revision first. The latest
successful update takes effect. Legacy revision fields are optional and ignored.

On creation, omitted or null `fileAccess` inherits. For an existing resource, omission
leaves the override unchanged; explicit null clears it. A
policy replacement is not a merge of its previous fields. Policy updates permit one document per request and cannot be mixed with ordinary metadata
or callback changes. Existing-ID ingest/retry does
not replace saved policies; use the update operation. Read back the confirmed policy before
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
splitting and crawl expansion. An explicit public override takes priority over broader protection settings.

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
| 409 | Check ownership and source state and reconsider the mutation before resubmitting. |
| 503 | Honor `Retry-After`; protection remains fail-closed while trustworthy state is unavailable. |

Policy updates commit in one transaction. A precommit failure keeps the previous
settings. After a timeout or lost response, read the current settings
before retrying: commit may have succeeded.
There is no pending-policy workflow or background recovery.

`POST /v1/ingest/document/{documentId}/retry` retries the currently failed HTTP delivery callback using saved output and callback settings. **202** returns `{ "documentId": "DOCUMENT_ID", "status": "processing" }`;
acceptance is not completion. Reread document status and delivery evidence. A 409 means
the current state is not eligible; do not automatically re-ingest or repeat the retry.
Historical source repair is an operator procedure, not a customer API or MCP operation.
