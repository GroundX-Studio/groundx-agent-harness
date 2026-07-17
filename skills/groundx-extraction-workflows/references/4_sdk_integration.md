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
│   Used by: compile_workflow.py when installed   │
│   Installed via: pip install groundx[extract]  │
├────────────────────────────────────────────────┤
│  groundx (Fern-generated core client)          │
│   GroundX, Document, WorkflowEngine,           │
│   WorkflowPrompt, WorkflowPromptGroup,         │
│   WorkflowStepConfig, WorkflowStep,            │
│   WorkflowSteps                                 │
│   Used by: groundx-api skill (workflow CRUD,   │
│            ingest, polling, get_extract)        │
│   Installed via: pip install "groundx[extract]" │
└────────────────────────────────────────────────┘
```

This skill uses the `[extract]` extra for deploy/run workflows and prefers it at
compile time when installed. `compile_workflow.py` also carries a narrow
SDK-free fallback for harness-authored `workflow.custom_steps` YAML so offline
CI and plugin validation do not depend on the published SDK being installed.
**No API calls happen during compile.**

For local deploy and run commands, this skill uses the GroundX Python
SDK. For interactive agent API calls (workflow create/update/attach,
ingest, poll, get_extract), this skill delegates operation semantics to
the `groundx-api` skill. Use the selected environment's `GROUNDX_API_KEY`
with the Python SDK by default. Live structured extraction currently runs in
prod; do not use dev for deploy + ingest + poll + get_extract unless an
operator explicitly confirms dev extraction is available. For dev
non-extraction API/debug calls, set
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`; for prod, leave it unset.
GroundX MCP is optional and prod-only.

Product YAML upload is a separate platform path. It accepts authored YAML,
normalizes it when needed, persists the effective source/metadata, and creates
or updates the workflow server-side. Use that path when proving user/product
upload behavior, especially internal legacy YAML-to-v1 normalization. The local
SDK paths below send compiled workflow bodies and cannot prove upload-time
normalization.

## 2. The compile script

### 2.1 What compile_workflow.py does

The script (`skills/groundx-extraction-workflows/templates/compile_workflow.py`)
executes the following sequence when invoked as
`python compile_workflow.py prompt.yaml > workflow.json`:

1. **Load env.** Reads `.env` for `EXTRACT_MODEL_*` engine settings when
   `python-dotenv` is installed; otherwise it uses the process environment and
   built-in defaults.
   `GROUNDX_API_KEY` is not required at compile time; a
   placeholder is acceptable since no API call is made.
2. **Load YAML.** The SDK prepares final groups, workflow groups, route
   metadata, and persisted extract metadata when available. If the SDK is not
   installed, the compiler uses its built-in fallback for harness-authored
   `workflow.custom_steps` YAML only.
3. **Validate harness metadata.** The compiler requires
   `extraction_policy_version: v1`, `workflow.custom_steps`,
   `workflow.agent_chain`, group-level `workflow_step:`, and field-level
   `workflow_output_key` where direct custom output routing is needed.
4. **Build workflow settings.** The compiler emits `extract`, explicit `null`
   built-in extraction `steps`, plus `template`, `customSteps`, `outputRoutes`,
   and `leafFields` from prepared metadata. For custom extraction workflows,
   `extract.workflow` must carry the persisted `custom_steps`, `output_routes`,
   and `leaf_fields` metadata that matches those top-level fields. It also
   renders each custom step's prompt text into the custom step config.
5. **Assemble the final dict.** The output is a Python dict with workflow create
   or update settings. The deploy and run templates pass it through
   `workflow_sdk_kwargs(workflow)`.
6. **Emit JSON to stdout.** `json.dumps(workflow, indent=2)` is
   written to stdout. Stderr is unused on success.

The output is the exact body shape that POSTs to `/v1/workflow`.

### 2.2 Custom step templates

The prompt text for custom workflow steps is prepared from the compiled YAML
metadata. When the SDK is installed, `groundx.extract` owns the YAML
preparation. When the SDK is absent, `compile_workflow.py` uses the same
harness-specific metadata contract for offline validation. In both paths, the
harness compiler renders the final custom step prompt wrappers before emitting
workflow JSON. It does not load a second prompt-wrapper module or re-parse the
raw path through a high-level SDK helper after compilation.

The custom workflow shapes the templates handle:

- **statement-style** — one flat object through a custom step with
  `kind: instruct`
- **charges-style** — array of records through a custom step with `kind: keys`
- **meters-style** — array of physical-meter or metered-usage records through a
  custom step with `kind: summary`

`kind: summary` is still an array-of-records shape. It is the summary step
family, not a request for one document summary object.

Each compiled custom step gets a `config` prompt for `figure`, `paragraph`, and
`table-figure` molecules, with `includes.pageImages: true`. The compiler uses
one reusable request template and one reusable task template, following the
shared custom-manager shape without copying utility-bill wording. The rendered
`request` message contains the document request, extraction guidelines, group
definition, field specs, output contract, and JSON-only final notes. The
rendered `task` message identifies the assistant, defines evidence and process
rules, lists concise field bullets, and states the parser-safety contract. If a
YAML authors a molecule-specific prompt in `custom_steps[].config`, the
compiler preserves it for that molecule and fills only the missing molecule
prompts.

Compiled extraction workflows set `doc-summary`, `doc-keys`, `sect-summary`,
`sect-instruct`, `chunk-summary`, and `chunk-instruct` to `null` in top-level
`steps`. That intentionally disables stock extraction prompts so runtime output
comes from the configured custom steps.

If the document type does not fit one of these shapes, still prefer custom
workflow metadata (`workflow.custom_steps`, `workflow_step`,
`workflow_output_key`) over editing compiler branches. The compiler emits
`customSteps`, `outputRoutes`, and `leafFields` when the prepared YAML carries
custom workflow metadata.
See §3.2 below.

### 2.3 Prompt-manager wrapper methods

For pilots that keep separate prompt modules, use `templates/prompt_manager.py`
as the thin lifecycle manager. Supported extract wrapper names are:

- `prompt_statement_extract_request(field_specs)`
- `prompt_statement_extract_task(field_descriptions)`
- `prompt_charges_extract_request(field_specs, group_definition)`
- `prompt_charges_extract_task(field_descriptions)`
- `prompt_meters_extract_request(field_specs, group_definition)`
- `prompt_meters_extract_task(field_descriptions)`

Reconcile and QA wrappers stay in the manager layer; see `prompt-manager.md`.

## 3. Customizing the compile script

### 3.1 Different group names

If the YAML uses group names other than `statement`, `charges`, and `meters`,
do not add group-name branches to the compiler. Use `workflow.custom_steps`,
`workflow_step:`, and `workflow_output_key`. The compiler stays domain-agnostic
and consumes prepared workflow metadata.

### 3.2 Different document types

For non-invoice documents (forms, receipts, contracts, reports), the
schema-first runner shape is still applicable: per-document fields usually use
custom `kind: instruct` steps, repeating records use `kind: keys`, and
physical-meter or metered-usage records use `kind: summary`. Both `keys` and
`summary` produce repeated record arrays.
The `workflow.agent_chain` branches still reference the workflow group names,
while task names stay internal runtime roles.

If a customer repo already has `manager.py`, `simple.yaml`, and separate
`extract_statement.py`, `reconcile_statement.py`, and `qa_statement.py` prompt
modules, prefer `templates/prompt_manager.py` over rewriting the project into
compiler branches. That shape keeps the migration path clear for a future
`groundx-python/extract` abstraction.

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

There are three local/agent execution paths, plus the product YAML upload path:

- **Deploy-only local script:** `templates/deploy_workflow.py` compiles,
  validates, creates or updates the workflow, and optionally attaches it
  to a bucket or account default through the GroundX Python SDK.
- **Full local runner:** `templates/run_extraction.py` performs deploy,
  ingest, status polling, X-Ray capture, and extract retrieval through
  the GroundX Python SDK. Use it against prod unless an operator confirms dev
  extraction is available.
- **Interactive agent operation:** use `groundx-api`; use MCP tools only when
  they are already connected in prod, otherwise use the Python SDK/API path.
- **Product YAML upload:** use the platform upload path when the behavior under
  test is raw YAML upload, normalization, persisted source, or user-facing
  workflow creation.

For first-run deploy guidance, use `deploy.md`. It has the short decision table
for MCP vs `deploy_workflow.py` vs `run_extraction.py`.

Once `workflow.json` is produced, the rest of the lifecycle uses
GroundX workflow and document operations. The full set of operations:

| Step | Operation | Where documented |
|---|---|---|
| Load reusable workflow settings | `client.load_extraction_definition(path=...)` / `client.load_extraction_definition(workflow_id=...)` | public Python SDK docs |
| Create workflow | `client.create_extraction_workflow(...)` (preferred SDK helper) / `workflows.create()` fallback / `workflow_create` when prod MCP is already connected | `skills/groundx-api/references/06-workflows.md` |
| Update workflow | `client.update_extraction_workflow(...)` (preferred SDK helper) / `workflows.update()` fallback | same |
| Attach workflow to bucket | `workflow_add_to_id` / `workflows.add_to_id()` | same |
| Ingest a local PDF | `gx.ingest()` SDK helper or pre-signed upload, then `document_ingestremote` for the hosted URL | `skills/groundx-api/references/02-documents.md` |
| Poll status | `document_getprocessingstatusbyid` / `GET /v1/ingest/{processId}` | same |
| Retrieve extraction | `document_getextract` / `documents.get_extract()` / `GET /v1/ingest/document/extract/{documentId}` | same |
| Inspect raw chunks (debug) | `document_getxray` / `documents.get_xray()` / `GET /v1/ingest/document/xray/{documentId}` | same |

For an iteration that involves only prompt changes, after the
workflow is created once, subsequent iterations use `workflow_update`
rather than `workflow_create`. The compile output is the same shape
either way; only the API operation changes.

The local Python templates compile first and then call
`workflows.create/update` with `workflow_sdk_kwargs(workflow)`. Do not compile a
YAML and then pass the same raw path back through
`create_extraction_workflow(path=...)`; that second parse bypasses the harness
compiler contract for `workflow_step:`, custom routes, and metadata-aware pilot
YAML. The high-level SDK helpers remain the preferred public SDK surface for
YAML that is directly SDK-loadable.

Do not treat this local compiled path as proof that product YAML upload works.
Certification and regression evidence for upload behavior must use the platform
YAML upload path and record that workflow creation path explicitly.

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
  rendered prompt text format, custom step routing, output routes,
  leaf fields, and page-image include behavior. The output is a
  wire-format JSON that can be POSTed by anyone.
- **Workflow API operations are not unique** to this skill — they are
  documented once, in `groundx-api`, and consumed by anything that
  needs them (this skill, UI implementation skills, future skills).

If GroundX changes the workflow API surface, only `groundx-api`
updates. If the schema authoring conventions evolve (e.g. a new
custom step kind, a new group name pattern), only this skill
updates. Each skill stays in its lane.
