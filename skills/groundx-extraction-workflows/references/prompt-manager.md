# Prompt Manager Today Path

This is the practical bridge for extraction pilots that need to work now. The
longer-term direction is for `groundx-python/extract` to turn one YAML into the
full extraction flow. Until that abstraction exists, use this convention to keep
customer code small and migration-friendly.

## 1. The Shape To Aim For

Keep `prompt.yaml` as the source of truth. Add thin Python wrappers only where
the domain needs prompt wording that the default compiler cannot express.

```
prompt.yaml
prompts/
  extract_statement.py
  reconcile_statement.py
  qa_statement.py
manager.py
```

The manager owns orchestration. The wrappers own language. The YAML owns final
fields and optional workflow grouping. Do not put real GroundX API keys in any
of these files.

## 2. Wrapper Function Contract

For a workflow group, the compile template can load external extract wrappers
from `EXTRACT_WRAPPER_MODULE`. Wrapper names are keyed by workflow group name,
not necessarily final output group name when `_pseudo_groups` are used:

```bash
EXTRACT_WRAPPER_MODULE=prompts.extract_statement \
python skills/groundx-extraction-workflows/templates/compile_workflow.py prompt.yaml
```

The module may define:

```python
def prompt_statement_extract_request(field_specs: str) -> str: ...
def prompt_statement_extract_task(field_descriptions: str) -> str: ...
```

Repeating groups use the same pattern:

```python
def prompt_charges_extract_request(field_specs: str, group_definition: str) -> str: ...
def prompt_charges_extract_task(field_descriptions: str) -> str: ...
def prompt_meters_extract_request(field_specs: str, group_definition: str) -> str: ...
def prompt_meters_extract_task(field_descriptions: str) -> str: ...
```

For reconcile and QA stages, keep explicit functions beside the extract
wrappers. These functions may run against workflow-group intermediate output,
final reassembled output, or both, but the boundary must be explicit:

```python
def prompt_statement_reconcile(*, candidate_json: dict, xray_context: dict) -> str: ...
def prompt_statement_qa(*, reconciled_json: dict, field_keys: list[str], field_prompts: dict) -> str: ...
```

The harness does not force exact argument names for reconcile/QA yet. It does
require the manager to make the inputs explicit: candidate state, field keys or
prompts, and source-document evidence such as page images or X-Ray context.

## 3. Manager Methods

Use `templates/prompt_manager.py` as the minimal adapter. A customer manager
should expose the same concepts even if method names differ:

- `workflow_body(yaml_path, workflow_name=None)` — compile YAML and wrappers to a
  workflow body
- `workflow_steps(...)` and `workflow_extract_dict(...)` — expose the compiled
  workflow slots and extraction schema separately for readback/comparison tests
- `prompt_statement_extract_request(...)`, `prompt_statement_extract_task(...)`,
  `prompt_charges_extract_request(...)`, `prompt_charges_extract_task(...)`,
  `prompt_meters_extract_request(...)`, and `prompt_meters_extract_task(...)`
  — default per-group extract wrapper methods that projects can override or
  replace with external wrapper modules
- `prompt_statement_reconcile(...)` and `prompt_statement_qa(...)` — minimal
  reconcile/QA wrapper methods that make candidate state and evidence explicit
- `init_prompts(...)` — create a workflow
- `update_prompts(...)` — update an existing workflow
- `list_workflows()` and `check_workflow(...)` — inspect registered workflows
- `add_to_account(...)` / `remove_from_account()` — manage account default
- `add_to_id(...)` / `remove_from_id(...)` — manage bucket attachment
- `ingest_and_debug(...)` — ingest a file and capture both `get_extract` and
  `get_xray`

`groundx-api` remains the source of truth for endpoint semantics. This reference
owns the extraction-specific order and the manager convention.

Custom managers should call or mirror the shared SDK preparation contract:

```python
from groundx.extract import prepare_extraction_yaml
```

Use prepared workflow groups for prompt rendering and workflow JSON. Use
prepared final groups plus `workflow_field_paths` for reassembly, requiredness,
QA, and final output. Do not reimplement pseudo-group routing or slot inheritance
inside a customer manager.

## 4. Workflow Management Sequence

For a new prompt schema:

1. Compile the YAML and wrappers into workflow JSON and
   `extraction_workflow_metadata_v1.json`.
2. Validate the workflow JSON shape.
3. Create the workflow.
4. Check the workflow by reading it back and confirming prompt slots are present.
5. Attach to the account default only if the pilot needs account-level default
   behavior.
6. Attach to the test bucket.
7. Ingest the test document.
8. Poll until complete.
9. Retrieve extract output.
10. Retrieve X-Ray output.
11. Reassemble workflow output into the final data object when route-map
    metadata is present.

For a prompt edit, use `update_prompts` rather than creating a new workflow.
Detach with `remove_from_id` or `remove_from_account` when a pilot should no
longer use the workflow.

## 5. Debug Loop

When output is wrong or empty, inspect evidence before rewriting prompts:

1. Check document status and confirm the ingest completed.
2. Retrieve `get_extract` and inspect the structured result.
3. Retrieve `get_xray` and inspect the source chunk evidence.
4. Compare the initial extraction result shape against the expected workflow
   shape and, after reassembly, the expected final output shape.
5. Use section summary, suggested text, and chunk evidence to decide whether the
   YAML field prompt, wrapper prompt, or downstream reconcile/QA prompt needs the
   change.

Only tighten the YAML or wrappers after that inspection. Re-ingest only when the
workflow prompt changed; use captured X-Ray for local comparison and debugging
when possible.

## 6. Migration To The Future Path

This today path is deliberately close to the future `groundx-python/extract`
direction:

- YAML stays durable.
- Prompt wrappers are thin and named by stage.
- Workflow lifecycle operations are centralized in one manager.
- Debug evidence is captured in a predictable shape.

As the SDK abstraction grows, the customer should be able to replace manager
glue with `groundx-python/extract` calls while keeping most of the YAML and
prompt-stage intent.
