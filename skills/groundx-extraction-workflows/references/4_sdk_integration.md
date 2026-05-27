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

For the API calls (workflow create/update/attach, ingest, poll,
get_extract), this skill delegates to the `groundx-api` skill. That
skill is the canonical reference for those operations. Follow its
MCP-first execution rule: try GroundX MCP tools, ask the user to connect
the GroundX MCP connector to GroundX when tools are missing, call
`groundx_account_context` when connected, and use SDK/REST only when the
connector cannot attach/authenticate or the required tool is missing.

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
   `_statement_task`, `_charges_request`, `_charges_task`).
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

The four wrapper templates that turn rendered field specs into LLM
messages live as module-level functions in `compile_workflow.py`, not
as separate Python files. This keeps the user's working directory
small — the only Python files copied in are `compile_workflow.py` and
`compare.py`.

The two shapes the templates handle:

- **statement-style** — one flat object, `chunk_instruct` slot, the
  step config has `field="sect-sum"`
- **charges-style** — array of records, `chunk_keys` slot, the step
  config additionally injects the rendered group definition as an
  "Extraction Guidelines" section

Both shapes use the same identity ("structured-data assistant"), the
same process steps, and the same output contract (return only JSON).

If the document type does not fit either shape, edit the wrapper
templates inline rather than working around them. See §3.2 below.

## 3. Customizing the compile script

### 3.1 Different group names

If the YAML uses group names other than `statement` and `charges`,
the compile script will not auto-wire them. The fix is local: edit
`_CompileManager.workflow_steps_for_yaml` and add new branches that
build steps for the new group names.

### 3.2 Different document types

For non-invoice documents (forms, receipts, contracts, reports), the
schema-first runner shape is still applicable: per-document fields go
in a chunk_instruct group, repeating records go in a chunk_keys
group. What typically needs to change is the wrapper template wording
(the `Identity` and few-shot examples). Edit the inline template
functions to match the document genre.

For documents that do not fit either shape (e.g. hierarchical
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

## 4. The workflow lifecycle (delegated to groundx-api)

Once `workflow.json` is produced, the rest of the lifecycle uses
`groundx-api`. The full set of operations:

| Step | Operation | Where documented |
|---|---|---|
| Create workflow | `workflow_create` (MCP first) / `workflows.create()` (SDK) / `POST /v1/workflow` (REST fallback) | `skills/groundx-api/references/06-workflows.md` |
| Update workflow | `workflows.update()` / `PUT /v1/workflow/{id}` | same |
| Attach workflow to bucket | `workflow_addtoid` / `workflows.add_to_id()` / `POST /v1/workflow/{bucketId}` | same |
| Ingest a local PDF | `gx.ingest()` SDK helper or pre-signed upload, then `document_ingestremote` for the hosted URL | `skills/groundx-api/references/02-documents.md` |
| Poll status | `document_getprocessingstatusbyid` / `GET /v1/ingest/{processId}` | same |
| Retrieve extraction | `document_getextract` / `documents.get_extract()` / `GET /v1/document/{id}/extract` | same |
| Inspect raw chunks (debug) | `document_getxray` / `documents.get_xray()` / `GET /v1/document/{id}/xray` | same |

For an iteration that involves only prompt changes, after the
workflow is created once, subsequent iterations use `workflow_update`
rather than `workflow_create`. The compile output is the same shape
either way; only the API operation changes.

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
