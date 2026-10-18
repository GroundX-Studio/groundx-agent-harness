# Protected files on a local deployment

Protection requires compatible API, FileAccess gateway, upload/layout workers and
extraction SDK images, private storage origins, encrypted transport and the selected
backend's acceptance evidence. Chart rendering or an API source branch proves none of
those deployment gates. Keep the feature disabled until the release gates pass.

Use the deployment's own `AGENTS.md` and
[`docs/agents/private-file-access.md`](https://github.com/eyelevelai/groundx-on-prem/blob/b7539d92c67def7185059286dad6faa7dd65c9f9/docs/agents/private-file-access.md)
for the candidate chart contract. Verify the chosen released chart/image refs before
copying its settings. That reference owns activation, migration, credentials, transport,
origin inventory and rollback; do not duplicate an operator runbook in application code.

## Deployment boundaries

- `fileAccess.enabled` defaults false. Enabling adds a streaming file gateway, with
  bandwidth and capacity cost. Use a stable HTTPS `publicUrl` and private HTTPS
  `storageEndpoint`; `signingEndpoint` is the native S3 API origin, separate from a
  store UI and the file delivery gateway. Preserve signed Host/path/query.
- Configure storage credentials and CA trust through the chart's Secret references.
  GroundX customer keys are not native-store credentials. Keep GroundX auth headers
  off native storage, and preserve them only on authenticated gateway requests.
- Forward file paths and `view=links` unchanged. Bypass caches and honor no-store.
  Verify HTTPS termination and its encrypted backplane before asserting
  `frontProxyTLSVerified`. `originsPrivate` is an operator assertion, not a bucket-policy
  mutation or evidence that anonymous GET/HEAD are denied on every alias.
- Pin the exact store release/digest, chart/operator version, gateway and worker images.
  Native S3, MinIO, AIStor and S4 need independent transport/read/upload/sign/expiry
  checks. Do not treat S3 compatibility or a Helm render as vendor certification.
- Upgrade legacy HTTP links to HTTPS before adding auth headers. Do not send credentials
  to an HTTP redirect. Historical source repair remains an operator-owned procedure.

## Local API and MCP use

Use the local API base and local MCP hostname from the installed deployment. Every upload uses the local API and configured storage, for public and protected
files. Upload issuance does not require `fileAccess.enabled`. Set `file.signingEndpoint`
when public upload recipients need a different native origin; enabled protection
continues to use `fileAccess.signingEndpoint`. New clients do not fall back to a hosted
upload broker. Verify local discovery exposes
`Customer_update`, `Bucket_create`, `Document_ingestRemote`, `Documents_fileLink` and
`Buckets_fileUpload` with the current schemas and scopes before relying on them.
Use `groundx-mcp/references/07-file-access.md` for the standalone list/describe/call flow,
or `groundx-api/references/13-file-access.md` for REST semantics.

Create protected buckets and files with initial `fileAccess`; omitted/null inherits,
creation has no prior revision, and later changes require confirmed revisions. Ancestors
cannot be weakened. Choose private bucket-owned staging before bytes whenever inheritance
or the requested file override is protected, even for a protected file in a public bucket.
Keep per-file overrides through split/crawl/bulk preparation. Verify the installed SDK's
private-upload implementation and initial-policy models; use explicit REST otherwise.

For acceptance, prove ordinary public and protected paths separately: anonymous denial,
authenticated stable reads, private PUT then ingest, a saved page share and expiry,
search-citation refresh, raw X-Ray capture versus `view=links`, owner isolation and
fail-closed dependency failure. Native grants remain reusable until expiry despite key
revocation or policy changes. Record actual deployed identities and outcomes; do not
promote source/local-test results to live acceptance.
