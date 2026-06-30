# GroundX API Debugging

Use this reference when a customer-scoped GroundX API operation appears stuck, incomplete,
empty, or inconsistent. Start from API-visible evidence. Do not guess internal causes.

## 1. Start With Evidence

Collect the smallest useful evidence bundle before proposing a retry, repair, or rerun:

- process ID returned by ingest or document-management operation
- document ID, bucket ID, group ID, or explicit document-set target
- current `document_getprocessingstatusbyid` response, including `status`,
  `statusMessage`, `progress.complete`, `progress.errors.total`,
  `progress.processing`, and `progress.queued`
- `document_lookup` or `document_get` output for affected documents
- callback response or callback error, if callbacks were configured
- timestamps, request shape, response shape, and visible error text
- search query, filters, relevance, verbosity, result IDs, and source citation payload

If any required identifier is missing, ask for it. Do not invent IDs, buckets, groups,
callbacks, filters, or status values.

Try GroundX MCP tools first. If the tools are not visible, say that the connector is not
attached and ask the user to connect the GroundX MCP connector. Use REST fallback only
when the connector cannot be attached now or the needed MCP tool is still unavailable.

## 2. Stuck Ingest Or Status

Use this path for documents stuck in `queued`, `training`, `processing`, or for a batch
that says `complete` while individual files are still missing, cancelled, or errored.

1. Read `02-documents.md` §5 and `08-errors-and-limits.md` §2.
2. Poll `document_getprocessingstatusbyid` / `GET /v1/ingest/{processId}`.
3. Inspect `status`, `statusMessage`, `progress.complete`, `progress.errors.total`,
   `progress.processing`, `progress.queued`, and `progress.cancelled`.
4. Use `document_lookup` for the process, bucket, or group, then `document_get` for any
   specific document ID that looks wrong.
5. Treat `complete` with `progress.errors.total > 0` as partial success, not clean
   success.
6. Do not re-ingest, cancel, retry, replay, or repair until the current status and saved
   identifiers have been checked.

If the API-visible evidence shows the operation is still in flight, report that state and
the next polling interval. If it shows `error` or document-level errors, preserve the
`statusMessage` and affected document IDs.

## 3. Empty Search Or Bad Citations

Use this path when search returns no results, weak results, a wrong page, or a source
viewer/citation payload that does not match the expected document.

1. Confirm the relevant ingest is complete and has no document-level errors.
2. Confirm the exact search target: bucket, group, single document ID, or explicit
   document set. Never invent a customer-wide search.
3. Preserve the query, filters, relevance, `n`, verbosity, result IDs, and source citation
   payload.
4. Read `03-search.md`, then `../guides/03-search.md` and
   `../guides/08-source-view-ui.md`.
5. If filters are present, read `../guides/07-filter-field.md` and confirm they cannot
   exclude the expected document.
6. If source metadata is missing, confirm verbosity is high enough for the needed fields.

Do not rewrite prompts, lower relevance, re-ingest, or label the result a platform bug
until target, filter, status, and result payload evidence has been checked.

## 4. Workflow-Backed Documents

For schema-first extraction YAML, compiled workflow JSON, field accuracy, or comparing
extracted output to expected answers, start in `groundx-extraction-workflows`.

Use this skill only for the platform API parts: workflow CRUD, bucket attachment,
document ingest, status polling, document lookup, and extraction-result retrieval.

## 5. Escalation Boundary

Public API debugging stops at a sanitized evidence bundle when the next step requires
hosted-service operator-only systems or private deployment controls.

The escalation bundle should include:

- affected account or project context, without secrets
- process ID, document ID, bucket/group/document-set target, and workflow ID if relevant
- current status response and affected document rows from API responses
- search request and response payload when search or citations are involved
- callback error or HTTP response body, if present
- exact UTC timestamps and the user's observed symptom

Do not include API keys, cookies, OAuth tokens, presigned URLs, private customer content,
or credentials in the bundle.

## 6. Stop Rules

- Do not guess root cause without current API evidence.
- Do not re-ingest or retry failed files before checking saved identifiers and current
  status.
- Do not claim success from a top-level `complete` status without checking
  document-level errors and output evidence.
- Do not name internal repositories, private paths, private operator systems, repair
  commands, or production-only tools.
- If the deployment is self-managed and the evidence points at pods, Helm, values.yaml,
  or cluster runtime, route to `groundx-on-prem`.
