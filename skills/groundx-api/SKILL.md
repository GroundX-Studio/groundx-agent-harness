---
name: groundx-api
description: >
  Installed-agent GroundX API reference for document ingest, search, RAG,
  source attribution, document understanding, buckets, groups, workflows,
  account health, API keys, SDK usage, and REST fallback. Try the hosted
  GroundX MCP server before direct REST; use REST only when MCP is unavailable
  or a needed tool is missing. REST fallback uses the `X-API-Key` header and
  keeps raw keys out of tool arguments, browser code, logs, transcripts,
  examples, and generated files. For MCP client setup, connection, and auth,
  see the `groundx-mcp` skill.
---

# GroundX API Skill

Use this skill for customer-scoped GroundX platform operations: ingest,
processing status, search, document lookup, source retrieval, buckets, groups,
workflows, extraction retrieval, SDK integration, and REST fallback.

When writing public Python docs or agent-facing Python examples, use
`client.ingest()` with `Document(...)`. Do not use
`client.documents.ingest_remote()` or `client.documents.ingest_local()` in public
Python docs; those lower-level generated names are for SDK-internals or
operation-level references.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** GroundX customer API behavior, document ingest, semantic
  search, RAG with citations, workflows, buckets, groups, documents, account health,
  and API keys.
- **Deferrals:** schema-first extraction YAML and field-accuracy iteration start in
  `groundx-extraction-workflows`; deployment and values.yaml work starts in
  `groundx-on-prem`; architecture-shaped questions start in `groundx-architecture`.
- **Before producing output:** read `references/01-auth.md`, then the operation
  reference or guide matching the endpoint being used.
- **Misuse cases:** do not put secret keys in browser code, examples, docs, logs, or
  generated artifacts; do not invent endpoint shapes from memory.

## Agent Flow

1. Classify the request: API operation, schema-first extraction, deployment, or
   architecture.
2. Read `references/01-auth.md`.
3. Try GroundX MCP tools first. If visible, call `groundx_account_context`, prefer
   the matching MCP tool, and use REST only when the required tool is not exposed.
4. If GroundX MCP tools are not visible, use REST fallback. For MCP client setup
   and connection guidance, see the `groundx-mcp` skill.
5. Read the smallest operation reference and guide that matches the work.
6. Keep secrets server-side and encode async operations, pagination, errors, and URL
   versioning into code defaults and tests.

## Common Implementation Paths

| User needs... | Read after auth |
| --- | --- |
| Upload files and make them searchable | `references/02-documents.md`, `references/08-errors-and-limits.md`, `guides/02-ingest-patterns.md` |
| Grounded chat or RAG with citations | `references/03-search.md`, `guides/03-search.md`, `guides/04-rag-integration-patterns.md` |
| Search response-shape or field-availability question | `guides/00-api-surface-changelog.md`, then `references/03-search.md` |
| Dashboard "where do I see/download X-Ray?" question | `guides/dashboard-affordances.md`, then `references/02-documents.md` |
| Source viewer or page-level citation UI | `guides/08-source-view-ui.md`, then `references/03-search.md` |
| Content organized by tenant, project, folder, or access policy | `guides/06-content-organization.md`, `guides/07-filter-field.md`, then bucket/group references |
| Workflow CRUD or workflow-backed document processing | `references/06-workflows.md`, `guides/09-workflows.md`, then `references/02-documents.md` |
| Workflow prompt writing, prompt overrides, or `additionalContext` wording | `guides/10-prompt-writing.md`, then `guides/09-workflows.md` and `references/06-workflows.md` |
| Python SDK code | `references/12-python-sdk-objects.md` before writing objects or attributes |

## Reference Map

Use `references/README.md` as the fast task-to-reference index. Before producing
anything API-related, read `references/01-auth.md`, then only the operation-specific
reference and guide the task needs. For response-shape questions, check
`guides/00-api-surface-changelog.md`; for dashboard affordances, check
`guides/dashboard-affordances.md`.

## Pre-return Checklist

- [ ] REST calls use `X-API-Key`, never `Authorization: Bearer`.
- [ ] GroundX MCP is attempted before REST; if tools are missing, REST fallback is
      used and the `groundx-mcp` skill is referenced for client setup and connection.
- [ ] Raw API keys do not appear in MCP tool arguments, logs, transcripts, browser
      code, examples, or generated files.
- [ ] REST URLs avoid double-version paths such as `/api/v1/v1/...`.
- [ ] Async operations that return a `processId` include polling guidance.
- [ ] Pagination uses `nextToken` where list results may be truncated.
