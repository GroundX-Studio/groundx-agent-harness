# 4. SDK integration

Before any command here creates local output, read
[`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must
use the initializer's exact run root. Ad-hoc work uses one dedicated root.

## 6. One workflow authoring path

Cashbot is the only workflow validator and compiler. Harness and the GroundX
Python SDK submit the exact authored YAML to:

- `workflows.validate(name=..., yaml=...)`
- `workflows.create(name=..., yaml=...)`
- `workflows.update(id=..., name=..., yaml=...)`

Do not build, normalize, repair, or recompile workflow JSON locally. Never
derive roles, routes, relationships, prompts, aliases, or defaults from group
names. Save the server response as `workflow.json` for evidence only.

Product YAML upload is a separate caller of the same Cashbot compiler. Use that
path when testing upload persistence or internal legacy normalization.
The local SDK path cannot prove product upload behavior.

## Local source readers

`templates/_workflow_source.py` is intentionally small and non-authoritative.
It reads source YAML only for:

- custom-step levels used by the request-fanout estimator;
- authored final-field names used by field-coverage checks.

It does not read identity or relationship intent, validate or compile YAML, or
emit execution metadata.
Changing this boundary requires a server-compiler change, not another Harness
derivation path.

## Execution paths

| Need | Path |
| --- | --- |
| Validate, create, update, optionally attach | `deploy_workflow.py` |
| Deploy, ingest, poll, capture X-Ray, retrieve extraction | `run_extraction.py` |
| Repeat over documents and score | `batch_extraction.py` |
| Interactive API operations | `groundx-api` |
| Prove product upload or legacy normalization | Product YAML upload |

Local scripts and interactive agents use the Python SDK by default. MCP is
optional and prod-only. Configure `GROUNDX_API_KEY`; set `GROUNDX_BASE_URL`
only for a non-default API environment. Dev structured extraction does not
currently work. Use dev only when an operator confirms it supports the tested
extraction path. Delegate endpoint semantics to `groundx-api`.

## Output authority

`documents.get_extract()` is the only source of customer extraction output.
When present, save it unchanged as `output.json`. Harness writes no second
customer-output artifact and never mutates the response.

Always preserve `xray.json` when available, but never reconstruct customer
output from X-Ray. If server extraction is missing, report that fact and keep
the evidence. Do not invoke a local compiler, SDK reassembler, group-name
fallback, or legacy adapter.

## Extending workflows

Author new document types and arbitrary group names through explicit v1 YAML:
`extraction_policy_version`, `workflow.custom_steps`, `workflow_step`, and
`workflow_output_key`. Cashbot owns their meaning. Harness orchestration must
remain document-neutral.

If the compiler contract must change, update Cashbot first with server tests,
then submit the unchanged source through every caller. Do not add a parallel
Harness implementation.

## Ownership

| Concern | Owner |
| --- | --- |
| YAML validation and compilation | Cashbot |
| Workflow persistence and runtime definition | GroundX platform |
| Metadata persistence and dispatch | Cashbot |
| Generic identity deduplication, custom-output reassembly, and relationship selection | GroundX Python |
| Service-specific hosted policy | Owning hosted extraction service, using the shared SDK relationship selector |
| Source submission, fanout estimate, non-mutating scoring, evidence | Harness |
| Generated API models | Fern/OpenAPI source |
| Legacy compatibility | Internal compatibility adapter |

For deployment details, use [`deploy.md`](./deploy.md). For endpoint semantics,
use `groundx-api`.
