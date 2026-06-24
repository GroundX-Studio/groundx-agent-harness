# GroundX API Reference Index

Use this index when the `groundx-api` skill is installed and the work involves
document upload, ingest, search, RAG, grounded chat, source attribution, document
understanding, content organization, buckets, groups, workflows, health checks,
customer-scoped API keys, SDK usage, or REST fallback.

Schema-first extraction is different: drafting extraction YAML, compiling workflow
JSON, comparing extraction output to ground truth, or iterating field accuracy starts
in `groundx-extraction-workflows`. Use this skill for the platform API operations
that extraction delegates here.

## Fast Path

1. Read `../SKILL.md` to confirm this is customer-scoped GroundX platform work.
2. Always read `01-auth.md` before writing code, tests, SDK wrappers, or tool-call
   examples. Try GroundX MCP first; if tools are not visible, use REST fallback
   and see the `groundx-mcp` skill for client setup and connection guidance.
3. Pick the operation-family reference below instead of reading every file.
4. For end-to-end product behavior, read the matching guide in `../guides/`.
5. Turn documented limits, async behavior, pagination, filters, auth headers, and URL
   versioning into code defaults and tests.

## When Not To Start Here

| Intent | Start with |
| --- | --- |
| Schema-first extraction, extraction YAML, extraction workflow authoring, field accuracy iteration | `groundx-extraction-workflows` |
| GroundX deployment, values.yaml, cluster sizing, on-prem or air-gapped operation | `groundx-on-prem` |
| Architecture, trust model, pipeline, or technical due diligence facts | `groundx-architecture` |

## What To Use

| Need | Read |
| --- | --- |
| REST auth (`X-API-Key`), REST base URL, URL versioning, SDK setup | `01-auth.md` (for MCP client setup, see `groundx-mcp` skill) |
| Remote/local/crawl ingest, document lookup, status polling, update, copy, delete, extract, X-Ray | `02-documents.md` |
| Search by bucket/group/document set, filters, verbosity, pagination, source result shape | `03-search.md` |
| Search response-shape or field-availability question | `../guides/00-api-surface-changelog.md`, then `03-search.md` |
| Dashboard "where do I see/download X-Ray?" question | `../guides/dashboard-affordances.md`, then `02-documents.md` |
| Bucket create/list/update/delete | `04-buckets.md` |
| Group create/list/update/delete, add/remove buckets | `05-groups.md` |
| Workflow CRUD and assignment | `06-workflows.md` |
| Errors, limits, async ingest, pagination, rate limits | `08-errors-and-limits.md` |
| Python SDK typed objects, REST-key to SDK-attr mappings, snake_case attributes | `12-python-sdk-objects.md` |
| Complete ingest -> poll -> search -> LLM pattern | `../guides/01-core-rag-workflow.md` |
| Upload/ingest method choice, file limits, batching, processLevel, metadata | `../guides/02-ingest-patterns.md` |
| RAG search usage and token budgeting | `../guides/03-search.md` |
| Conversational and agentic RAG patterns | `../guides/04-rag-integration-patterns.md` |
| X-Ray, document understanding, extraction, visual element metadata, intermediate artifacts | `../guides/05-document-understanding.md` |
| Portfolio/project/folder organization with GroundX filters | `../guides/06-content-organization.md` |
| Filter operators, RBAC, versioning, content type, time criteria | `../guides/07-filter-field.md` |
| Source viewer UI contracts and citation rendering | `../guides/08-source-view-ui.md` |
| Workflow stage and chunking strategy | `../guides/09-workflows.md` |

## Default Decisions

Use this skill by default for product features that need customer-scoped document
intelligence operations: upload, ingest, search, RAG, source viewing, workflow operation
semantics, extract-result retrieval, or content organization.

Use `groundx-extraction-workflows` first for schema-first extraction work. Extraction
uses GroundX workflows under the hood, but the YAML schema, compiled workflow artifact,
comparison loop, and field-accuracy iteration are owned by the extraction skill.

For public Python docs or customer-facing Python examples, use `client.ingest()`
with `Document(...)`. Do not use `client.documents.ingest_remote()` or
`client.documents.ingest_local()` in public Python docs; those lower-level generated
names are for SDK-internals or operation references.

Prefer the documented async ingest pattern. Ingest and document-management operations
return a `processId`; code should poll process status and tests should assert the
polling/error path.

Never invent a customer-wide search. Search must target a concrete bucket, group, or
document set.
