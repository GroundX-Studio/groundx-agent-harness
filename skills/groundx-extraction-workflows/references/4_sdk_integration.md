# 4. SDK integration

How `compile_workflow.py` produces the workflow JSON, what
`groundx-api` does with it, and how to extend the boundary for
non-default cases.

## 1. Two SDK layers

```
┌────────────────────────────────────────────────┐
│  groundx.extract (hand-written extension)      │
│   PromptManager, Source, Logger, Group,        │
│   Prompt, ExtractedField                        │
│   Used by: compile_workflow.py                  │
│   Installed via: pip install groundx[extract]  │
├────────────────────────────────────────────────┤
│  groundx (Fern-generated core client)          │
│   GroundX, Document, WorkflowEngine,           │
│   WorkflowPrompt, WorkflowPromptGroup,         │
│   WorkflowStepConfig, WorkflowStep,            │
│   WorkflowSteps                                 │
│   Used by: groundx-api skill (workflow CRUD,   │
│            ingest, polling, get_extract)        │
│   Installed via: pip install groundx           │
└────────────────────────────────────────────────┘
```

This skill uses the `[extract]` extra at *compile* time only — to
parse the YAML and render the prompts into the typed workflow objects
the core SDK serializes. **No API calls happen during compile.**

For local deploy and run commands, this skill uses the GroundX Python
SDK. For interactive agent API calls (workflow create/update/attach,
ingest, poll, get_extract), this skill delegates operation semantics to
the `groundx-api` skill. Follow its MCP-first execution rule: try
GroundX MCP tools, ask the user to connect the GroundX MCP connector to
GroundX when tools are missing, call `groundx_account_context` when
connected, and use the Python SDK when local script execution is the
right path.

## 2. The compile script

### 2.1 What compile_workflow.py does

The script (`skills/groundx-extraction-workflows/templates/compile_workflow.py`)
executes the following sequence when invoked as
`python compile_workflow.py prompt.yaml > workflow.json`:

1. **Load env.** Reads `.env` for `EXTRACT_MODEL_*` engine settings.
   `GROUNDX_API_KEY` is not required at compile time; a
   placeholder is acceptable since no API call is made.
2. **Load YAML.** A thin `PromptManager` subclass (`_CompileManager`)
   takes the YAML's directory as its `Source` cache path and loads
   the schema by basename. The SDK parses the YAML into typed
   `Group` and `ExtractedField` objects.
3. **Render the prompt text for each group.** Per-field markdown
   blocks (description, format, identifiers, instructions) are
   concatenated and wrapped in the per-step user/developer message
   templates (the inline functions `_statement_request`,
   `_statement_task`, `_charges_request`, `_charges_task`,
   `_meters_request`, `_meters_task`) unless `EXTRACT_WRAPPER_MODULE`
   points at an external wrapper module.
4. **Build the typed workflow steps.** Each step config wires the
   rendered prompts into `WorkflowStepConfig` with the engine and
   `pageImages: True`, then wraps it in `WorkflowStep` for the three
   content types (`figure`, `paragraph`, `table_figure`).
5. **Assemble the final dict.** The output is a Python dict with four
   keys: `name`, `chunk_strategy`, `extract`, `steps`. The steps and
   extract dicts are produced by serializing the typed objects.
6. **Emit JSON to stdout.** `json.dumps(workflow, indent=2)` is
   written to stdout. Stderr is unused on success.

The output is the exact body shape that POSTs to `/v1/workflow`.

### 2.2 Inline wrapper templates

The six wrapper templates that turn rendered field specs into LLM
messages live as module-level functions in `compile_workflow.py`, not
as separate Python files. This keeps the user's working directory
small; `templates/prompt_manager.py` is available when a pilot needs a
thin manager around workflow lifecycle and custom wrappers.

The three shapes the templates handle:

- **statement-style** — one flat object, `chunk_instruct` slot, the
  step config has `field="sect-sum"`
- **charges-style** — array of records, `chunk_keys` slot, the step
  config additionally injects the rendered group definition as an
  "Extraction Guidelines" section
- **meters-style** — array of physical-meter or metered-usage records,
  `chunk_summary` slot, the step config has `field="chunk-sum"`

All three shapes use the same identity ("structured-data assistant"), the
same process steps, and the same output contract (return only JSON).

If the document type does not fit one of these shapes, prefer an external
wrapper module or the prompt-manager adapter before editing compiler templates.
See §3.2 below.

### 2.3 External wrapper modules

For quickstart-style pilots that already have separate prompt modules, keep
those modules and let the compiler load them:

```bash
EXTRACT_WRAPPER_MODULE=prompts.extract_statement \
python skills/groundx-extraction-workflows/templates/compile_workflow.py prompt.yaml
```

The environment variable may be a module path (`prompts.extract_statement`) or a
Python-file path relative to the YAML directory (`prompts/extract_statement.py`).
Supported extract wrapper names are:

- `prompt_statement_extract_request(field_specs)`
- `prompt_statement_extract_task(field_descriptions)`
- `prompt_charges_extract_request(field_specs, group_definition)`
- `prompt_charges_extract_task(field_descriptions)`
- `prompt_meters_extract_request(field_specs, group_definition)`
- `prompt_meters_extract_task(field_descriptions)`

Older aliases such as `statement_extract_request` and `extract_statement_task`
are accepted as compatibility names. Reconcile and QA wrappers stay in the
manager layer; see `prompt-manager.md`.

## 3. Customizing the compile script

### 3.1 Different group names

If the YAML uses group names other than `statement`, `charges`, and `meters`,
the compile script will not auto-wire them. The fix is local: edit
`_CompileManager.workflow_steps_for_yaml` and add new branches that
build steps for the new group names.

### 3.2 Different document types

For non-invoice documents (forms, receipts, contracts, reports), the
schema-first runner shape is still applicable: per-document fields go
in a chunk_instruct group, repeating records go in a chunk_keys
group, and physical-meter or metered-usage records go in a chunk_summary
group. What typically needs to change is the wrapper template wording
(the `Identity` and few-shot examples). Use an external wrapper module or
edit the inline template functions to match the document genre.

If a customer repo already has `manager.py`, `simple.yaml`, and separate
`extract_statement.py`, `reconcile_statement.py`, and `qa_statement.py` prompt
modules, prefer `EXTRACT_WRAPPER_MODULE` plus `templates/prompt_manager.py` over
rewriting the project into inline compiler functions. That shape works today and
keeps the migration path clear for a future `groundx-python/extract`
abstraction.

For documents that do not fit these shapes (e.g. hierarchical
reports, free-form correspondence), the schema-first runner is not
the right tool. Surface this and discuss the alternatives with the
user before authoring a workaround.

### 3.3 Different model

The model is configured via three env vars:

- `EXTRACT_MODEL_ID` — the engine identifier (default `gpt-5-mini`)
- `EXTRACT_MODEL_REASONING` — reasoning effort (default `high`)
- `EXTRACT_MODEL_SERVICE` — the model provider (default `openai`)

Higher reasoning effort produces measurably better extraction
accuracy at a latency cost. For accuracy-sensitive extractions
(billing, financial, compliance), keep reasoning at `high`. For very
simple extractions or high-volume runs, `medium` may be acceptable.

## 4. The workflow lifecycle

There are three execution paths:

- **Deploy-only local script:** `templates/deploy_workflow.py` compiles,
  validates, creates or updates the workflow, and optionally attaches it
  to a bucket or account default through the GroundX Python SDK.
- **Full local runner:** `templates/run_extraction.py` performs deploy,
  ingest, status polling, X-Ray capture, and extract retrieval through
  the GroundX Python SDK.
- **Interactive agent operation:** use `groundx-api` and prefer MCP
  tools when available.

For first-run deploy guidance, use `deploy.md`. It has the short decision table
for MCP vs `deploy_workflow.py` vs `run_extraction.py`.

Once `workflow.json` is produced, the rest of the lifecycle uses
GroundX workflow and document operations. The full set of operations:

| Step | Operation | Where documented |
|---|---|---|
| Create workflow | `workflow_create` (MCP first) / `workflows.create()` (SDK) | `skills/groundx-api/references/06-workflows.md` |
| Update workflow | `workflows.update()` | same |
| Attach workflow to bucket | `workflow_add_to_id` / `workflows.add_to_id()` | same |
| Ingest a local PDF | `gx.ingest()` SDK helper or pre-signed upload, then `document_ingestremote` for the hosted URL | `skills/groundx-api/references/02-documents.md` |
| Poll status | `document_getprocessingstatusbyid` / `GET /v1/ingest/{processId}` | same |
| Retrieve extraction | `document_getextract` / `documents.get_extract()` / `GET /v1/ingest/document/extract/{documentId}` | same |
| Inspect raw chunks (debug) | `document_getxray` / `documents.get_xray()` / `GET /v1/ingest/document/xray/{documentId}` | same |

For an iteration that involves only prompt changes, after the
workflow is created once, subsequent iterations use `workflow_update`
rather than `workflow_create`. The compile output is the same shape
either way; only the API operation changes.

`document_getextract` returns the workflow-defined JSON object exactly as
GroundX stored it. Do not assume a fixed vocabulary such as `amount_due` or
`recipient_name`; compare the returned top-level keys to the schema attached to
that document's extraction workflow.

`templates/deploy_workflow.py` is the deploy-only local script for finished YAMLs.
It reads `GROUNDX_API_KEY` from `.env` or environment and never accepts API keys as
command-line arguments. Use `--bucket-id` for an existing bucket ID, `--bucket-name`
for exact existing bucket-name lookup, and `--create-bucket-name` to create a bucket.
Use `--dry-run` to compile, validate, and write planned deploy metadata without API calls.
`templates/prompt_manager.py` centralizes the extraction-specific order for
these operations: create/update/list/check workflow, add/remove account default,
add/remove bucket attachment, ingest, poll status, retrieve `get_extract`, and
retrieve `get_xray`. Endpoint semantics still live in `groundx-api`; the manager
is the pilot-friendly adapter that keeps prompt iteration executable today.

## 5. Why the boundary lives where it does

The split between this skill and `groundx-api` is deliberate:

- **Schema authoring is unique** to this skill: group decomposition,
  field anatomy, identifiers/instructions craft. No other skill
  teaches this.
- **YAML→workflow JSON translation is unique** to this skill: the
  rendered prompt text format, the chunk_instruct vs chunk_keys
  routing, the page-images include. The output is a wire-format JSON
  that can be POSTed by anyone.
- **Workflow API operations are not unique** to this skill — they are
  documented once, in `groundx-api`, and consumed by anything that
  needs them (this skill, UI implementation skills, future skills).

If GroundX changes the workflow API surface, only `groundx-api`
updates. If the schema authoring conventions evolve (e.g. a new
content-type slot, a new group name pattern), only this skill
updates. Each skill stays in its lane.
