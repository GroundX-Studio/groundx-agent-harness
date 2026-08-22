# Workflow How-To

Before any command here creates local output, read [`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must initialize and use its exact absolute run root. Ad-hoc work uses one dedicated root. Settle or hand off useful results, delete raw evidence, verify absence, and report what remains.

Use this guide as the ordered path for a schema-first extraction job. It routes
each stage to the reference that owns the details instead of duplicating every
rule here.

## 1. Intake Resources

Read `customer-onboarding.md` and `13_customer_intake.md`.

Collect:

- Representative source documents.
- Field catalog with owner, scope, null rule, examples, and final output name.
- Expected answers for evaluation documents, in any source format.
- Output handoff owner and expected final JSON shape.
- Batch-readiness trigger and acceptance threshold.

Do not draft YAML until the target fields and expected-answer quality are clear
enough to score.

Before writing prompts, read `16_prompt_writing.md`, `prompt-quality.md`, and
`prompt-improvement-loop.md`. The first draft should already follow the full
process: locate source evidence, write reusable prompt rules, validate with the
server, run,
source-adjudicate misses, and improve one change at a time.

## 2. Design Final Groups First

Read `2_schema_design.md` and `prompt-quality.md`.

Real top-level YAML groups define the final data object. Keep these stable for
downstream consumers. `statement`, `charges`, and `meters` are useful invoice
defaults, but unrelated domains should choose final groups that match their
output contract. Keep top-level `extraction_policy_version: v1` in new
harness-authored workflow YAML.

Use mapping-shaped `prompt:` objects only. Keep `_defs` fields-only; reusable
prompt text belongs under a real final group.

## 3. Decide Workflow Grouping

Read `2_schema_design.md` section 1 and `3_prompt_pipeline.md`.

Use final groups directly when each group is small enough to run as one
workflow group. In harness-authored YAML, that real top-level group declares
group-level `workflow_step:`.

Keep each workflow group near 30 fields or fewer. If one final group grows too
large but the final JSON shape must stay stable, use `_pseudo_groups` as
workflow-only groups and route each pseudo field back to a real final field with
`path`. Split into real final groups only when that output shape is acceptable
to the user. Do not use `slot:`, `domain:`, or field-level `workflow_step`.

Estimate request fanout before choosing chunk-level execution. The planning
rule is `pages * chunks per page * chunk-level custom steps`; pseudo groups
reduce field and prompt load but pseudo groups at `level: chunk` still multiply
requests. If evidence shows expected documents are long, move
broad statement-style groups to `workflow.section_strategy: page` and
`level: section` when the chunk estimate approaches the 2000 request cap.

Add `workflow.agent_chain` before server validation. It is required. The first stage is
a `parallel` list with one branch per executable workflow group. Branch `group`
values are workflow group names; branch `chain` values are internal runtime task
names such as `reconcile_statement`, `qa_statement`, `save_statement`,
`reconcile_charges`, `save_charges`, `reconcile_meters`, `qa_meters`, and
`save_meters`.

## 4. Validate And Register

Submit authored v1 source YAML to the GroundX API for validation and
registration. Do not feed `workflow.json`, downloaded workflow readback, or
`_groundx_persisted_extract` back into the server compiler. The canonical
statement of authoring-path ownership is
[`4_sdk_integration.md`](./4_sdk_integration.md) §6.

Run:

```bash
python -c "import os; from groundx import GroundX; GroundX(api_key=os.environ['GROUNDX_API_KEY']).workflows.validate(name='pilot', yaml=open('prompt.yaml').read())"
```

For script-based validation, run, or deploy paths, use `deploy_workflow.py`,
`run_extraction.py`, or `batch_extraction.py`; these write both `workflow.json`
and `extraction_workflow_metadata_v1.json`.

`workflow.json.extract` is server readback saved with the run. It must preserve
the server's persisted extraction mapping, including YAML
metadata such as policy version, final-group relationship settings, and
custom workflow routing support when present. Do not strip it down to only
`fields` and `prompt`. The validator must pass before deploy, MCP
create/update, or ingest.

The metadata artifact carries:

- `workflow_field_paths`
- prepared final groups
- top-level metadata
- final-group metadata
- workflow-group metadata
- source YAML checksum

Keep this artifact with the server workflow readback and run output. It is useful for
local diagnostics and reassembly handoff, but it is not the only place authored
metadata survives.

## 5. Deploy Or Attach

Read `deploy.md`.

Use `deploy_workflow.py` for deploy-only SDK execution. Use `groundx-api` for
interactive workflow registration, bucket attachment, ingest, polling, and
extract retrieval. Do not copy API operation semantics into this skill.

`deploy_workflow.py` and direct `workflow_create` calls send the authored source
YAML. Record the actual entrypoint when evidence must distinguish SDK, MCP, or
product behavior.

## 6. Run Extraction And Inspect Evidence

Use `run_extraction.py` for one prod document or `batch_extraction.py` for a
live prod batch. Dev structured extraction does not currently work; use dev only
for non-extraction API/debug calls unless an operator explicitly confirms dev
extraction is available. Retrieve:

- `workflow.json`
- `extraction_workflow_metadata_v1.json`
- `output.json` when raw GroundX `get_extract` is available
- `xray.json`
- `xray_diagnostic.json` and `final_output.json` when local diagnostics were needed
- run log

When a field is wrong, inspect X-Ray and rendered request evidence before editing the
YAML. Read `10_debugging_methodology.md` for the diff-before-debug path and
`prompt-improvement-loop.md` for the one-change iteration loop.

## 7. Read Back Routes

The harness-supported path routes real workflow groups directly to final fields.
The route metadata still tells diagnostics and readback where each workflow field
lands in the final object:

Missing routed values are classified deliberately:

- Missing routed workflow group: reassembly error.
- Missing optional field inside a present workflow group: diagnostic partial
  data.
- Missing required field inside a present workflow group: QA/completeness
  failure with partial output retained for debugging.

Requiredness comes from the final field schema, not workflow-step names.

## 8. Apply Final Post-Processing

Read `12_business_logic.md`.

Run local dedupe, linking, conflict surfacing, and passthrough on final groups
unless a primitive is explicitly workflow-scoped. Do not attach final business
metadata to workflow step definitions.

## 9. Score And Iterate

Read `5_validation.md`, `prompt-improvement-loop.md`,
`8_iteration_and_feedback.md`, and `15_repeating_groups.md` for repeating
records.

Score final reassembled output against expected answers. Iterate one issue at a
time:

- Field prompt if one field is wrong.
- Workflow grouping or custom-step assignment if an agent is overloaded.
- Route map/reassembly if values land in the wrong final group.
- Business logic primitive if extracted values are correct but final acceptance
  is wrong.

## 10. Escalate The Right Boundary

Escalate primitive gaps separately from prompt, workflow grouping, or reassembly
gaps:

- Prompt or YAML issue: revise `prompt.yaml`.
- Workflow grouping issue: revise real groups or custom-step assignments.
- Platform workflow execution issue: record the compiler/platform constraint.
- Server-side Extract availability issue: use X-Ray fallback and record the
  environment limitation.
- Reassembly issue: preserve `extraction_workflow_metadata_v1.json` and the raw
  workflow output for the downstream reassembly handoff.
- New final business primitive: record the general primitive, not a
  one-customer fork.
