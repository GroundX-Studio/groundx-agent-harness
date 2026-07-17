# 1. The extraction loop

This is the default end-to-end loop the skill walks through. It is
single-file at the YAML layer, delegates execution to the GroundX API
(via the `groundx-api` skill), and is reproducible: same YAML + same
PDF + same compile output produces the same workflow JSON, which —
applied to the same document — produces the same extraction.

## 1. Overview

```
┌─────────────┐   compile    ┌──────────────┐
│ prompt.yaml │─────────────►│ workflow.json│
└─────┬───────┘              └──────┬───────┘
      │                             │
      │                             │ POST workflow + attach to bucket
      │                             │ (groundx-api: workflow_create,
      │                             │  workflow_add_to_id)
      │                             ▼
      │                      ┌─────────────┐
      │                      │  GroundX    │
      │                      │  workflow   │
      │                      └──────┬──────┘
      │                             │
┌─────▼──────┐  ingest+extract      │
│ input.pdf  │──────────────────────┤
└────────────┘                      │
                                    ▼
                            ┌──────────────┐
                            │ output.json  │ raw get_extract when available
                            └──────┬───────┘
                                   │ python score_extraction.py
                                   ▼
                          pass/fail/warn report
```

The user edits `prompt.yaml`. Everything downstream is mechanical:
`compile_workflow.py` produces the workflow JSON, `groundx-api`
operations register and run it, `score_extraction.py` evaluates accuracy.

## 2. Setup

Before the loop runs, the working directory must have:

1. `prompt.yaml` — copied from
   `skills/groundx-extraction-workflows/templates/prompt.yaml` and edited for the
   target document type
2. `.env` — copied from `skills/groundx-extraction-workflows/templates/.env.sample`
   and populated with `GROUNDX_API_KEY`
3. `compile_workflow.py` — copied from
   `skills/groundx-extraction-workflows/templates/compile_workflow.py`
4. `validate_workflow_json.py` — copied from
   `skills/groundx-extraction-workflows/templates/validate_workflow_json.py`
5. `deploy_workflow.py` — copied from
   `skills/groundx-extraction-workflows/templates/deploy_workflow.py` when the
   finished YAML needs workflow create/update and attachment
6. `run_extraction.py` — copied from
   `skills/groundx-extraction-workflows/templates/run_extraction.py` when the
   same command should also ingest, poll, capture X-Ray, and retrieve extract
7. `score_extraction.py` — copied from
   `skills/groundx-extraction-workflows/templates/score_extraction.py`
8. `run_extraction_loop.py` — copied from
   `skills/groundx-extraction-workflows/templates/run_extraction_loop.py` when
   the work is PDF plus desired schema plus expected answers and should iterate
   up to 10 times or until accuracy is at least 90%
9. `requirements.txt` — copied from
   `skills/groundx-extraction-workflows/templates/requirements.txt`
10. The input PDF (named anything; pass the path as needed)
11. Expected answers for scoring. If they are already runner-shaped JSON, use
    them directly as the expected-answer JSON file. If they arrive as a spreadsheet,
    document, text file, PDF, or human-review notes, create a source-backed
    mapping record before scoring.

A throwaway working directory under `/tmp` is fine for one-shot
extractions. A persistent directory (e.g.
`~/extractions/<customer>/`) is fine for ongoing iteration.

```bash
pip install -r requirements.txt
```

## 3. The loop

### 3.1 Draft the YAML

Read `16_prompt_writing.md`, `prompt-quality.md`, and §2 in
`2_schema_design.md` for the full prompt-writing path, prompt quality checklist,
group decomposition, and field anatomy. Author the YAML based on:

- The fields the user wants to extract (or, if expected answers are
  provided, the fields in the expected answers)
- One worked example to look at the document and identify each field's
  visual identifiers and edge cases
- Final groups that match the customer-facing JSON shape. Invoice-like
  documents often use `statement`, `charges`, and optional `meters`; claim
  forms, contracts, schedules, and other document types should use
  domain-aligned names such as `claim` and `line_items`.
- Matching `workflow.custom_steps` and either direct groups with group-level
  `workflow_step` plus `workflow_output_key`, or `_pseudo_groups` with
  `workflow_step` plus `path` routes.

If the document shape does not fit singleton objects or repeating record
lists, see `2_schema_design.md` §1.5.

### 3.2 Compile to workflow JSON

```bash
python compile_workflow.py prompt.yaml > workflow.json
python validate_workflow_json.py workflow.json
```

`compile_workflow.py` is offline — it does not call any GroundX API.
It loads the YAML, renders the field-spec text, and emits the
workflow JSON in the exact shape the GroundX workflow API accepts.
`validate_workflow_json.py` must pass before workflow create/update, MCP
registration, or ingest.

The resulting `workflow.json` is the durable artifact for this run.
Diff it across iterations to see exactly what the prompts look like
that the LLM will receive.

### 3.3 Deploy or run the workflow

Use the smallest path that matches the task.

**Deploy-only:** when the YAML is finished and you only need to register
or attach the workflow, use the local SDK deploy command:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out deploy/ \
  --workflow-name customer-workflow-v1 \
  --create-bucket-name customer-bucket-v1
```

`deploy_workflow.py` compiles the YAML, validates the workflow JSON,
creates or updates the workflow through the GroundX Python SDK, and can
attach it to a bucket or the account default. It writes `workflow.json`,
`deploy.json`, `workflow_id.txt`, and `bucket_id.txt` when applicable.
It is deploy-only; it does not ingest files, poll status, capture X-Ray,
or retrieve extract output.

This is the direct compiled SDK path. It is not proof of product YAML upload
behavior, persisted-source handling, or legacy YAML normalization. When the
claim is that uploaded YAML behaves correctly, use the platform YAML upload path
and record that path in the evidence.

Read `deploy.md` before running it. The short version: use `--bucket-id`
for an existing bucket ID, `--bucket-name` for an exact existing bucket-name
lookup, and `--create-bucket-name` when the command should create a new bucket.
Use `--dry-run` first when you want compile/validation and planned actions
without a live API call.

**Full local run:** when you need prod deploy + ingest + poll + X-Ray +
extract output, use `run_extraction.py`. Dev structured extraction does not
currently work; do not run this path against dev unless an operator explicitly
confirms it is available. The runner writes `output.json` only for the
raw GroundX `get_extract` payload. If raw extract is unavailable, it writes
`xray_diagnostic.json` and `final_output.json` instead. Add
`--require-raw-extract` when missing `output.json` should fail the run. The
runner ingests with `processLevel: full` so workflow execution is on the path.
If local
polling reaches `--max-polls`, the runner writes `timeout_summary.json` and a
bounded `timeout_history.json` with the process ID, workflow ID, bucket ID,
last status, scoreability, and a resume command. Resume the same process with:

```bash
python run_extraction.py --resume --out <run-dir>
```

Resume reads the run-local `workflow.json` and `business_logic_metadata.json`
when present. It does not recompile or re-read source YAML.

Do not redeploy, create a new bucket, attach a new workflow, or ingest the file
again just because local polling timed out. A timeout means the local wait
expired; the platform process may still complete.

**Bounded authoring loop:** when the user has supplied one or more PDFs, a
desired schema or YAML draft, and expected answers or reviewer notes mapped to
JSON, use `run_extraction_loop.py`. It composes `run_extraction.py` for each
iteration, requires raw `documents.get_extract` provenance before scoring,
records request-fanout evidence, YAML diffs, workflow/bucket/document/process
IDs, X-Ray/extract artifacts, `loop_state.json`, and `final_report.json`, and
stops when field-level accuracy is at least 90% or 10 iterations have run.

```bash
python run_extraction_loop.py \
  --yaml prompt.yaml \
  --pdf sample.pdf \
  --expected-json expected_answers.json \
  --out runs/sample-loop \
  --iteration-schema-dir iterations/
```

If the score is below 90%, inspect the PDF, X-Ray, raw extraction, score report,
and the compiled prompt/workflow diff. Make one prompt or group-rule change,
save it as `iterations/prompt.iteration-02.yaml` or `iterations/iteration-02.yaml`,
and continue. The runner reports `blocked` instead of retrying the same YAML
when no next revision is available.

**Interactive agent path:** when an agent is operating inside Claude or
Codex, follow `groundx-api` operation semantics with the selected
environment's `GROUNDX_API_KEY`. Use the GroundX Python SDK by default.
Full live extraction should target prod unless an operator confirms dev
extraction is available. For dev non-extraction API/debug calls, set
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`; for prod, leave it unset.
GroundX MCP is optional and prod-only. The extraction skill remains the schema
authoring reference; `groundx-api` remains the operation-semantics reference.

The manual operation loop is:

1. **Create or update the workflow.** POST `workflow.json` via the
   `workflows.create()` SDK call. In prod sessions where MCP is already
   connected, `workflow_create` is also acceptable. This is still the direct
   compiled workflow path, not the product YAML upload path. The response
   includes the `workflowId`.
2. **Attach the workflow to a bucket.** Either an existing bucket or a
   new one. Use the SDK call, or `workflow_add_to_id` when using prod MCP.
3. **Ingest the PDF.** For local PDFs, prefer the Python SDK ingest
   helper or the pre-signed upload flow from `groundx-api`, then submit
   the hosted URL through `document_ingestremote`. When the PDF is
   already hosted, use `document_ingestremote` directly. Do not make the
   legacy multipart local endpoint the default; it is a small-file REST
   fallback and is not exposed as a GroundX MCP local-file upload tool.
   The response includes a `processId`.
4. **Poll the ingest status.** Use `document_getprocessingstatusbyid`
   until the status is `complete`.
5. **Retrieve the extraction.** Use
   `documents.get_extract(document_id=...)` for the document the
   ingest produced. Save the JSON.

```bash
# After running steps 1-5 via groundx-api, save raw get_extract as output.json.
```

### 3.4 Compare to Expected Answers

```bash
python score_extraction.py output.json expected_answers.json
# If you are intentionally scoring local diagnostic output:
python score_extraction.py final_output.json expected_answers.json
```

The comparator reads expected-answer JSON in the runner output shape and emits a
structured report: PASS / FAIL / WARN per field, with the expected and
extracted values for any non-PASS row.
See §2 in `5_validation.md` for what each verdict means and how the
comparison logic treats casing, dates, floats, and arrays.

If expected answers arrive as a spreadsheet, document, text file, PDF, or
human-review notes, map them to runner-shaped JSON first. Record, per mapped
field: field path, expected-answer source location, normalized expected value,
extracted value, source-support decision, scoreability decision, and rationale.
Do not claim a final accuracy improvement unless the run produced a new raw
`output.json`, or the report is explicitly labeled as diagnostic/local-final.

### 3.5 Iterate

For every FAIL or WARN, identify the YAML field or group rule that produced it.
Use `prompt-improvement-loop.md`: source-adjudicate the disagreement, classify
the miss, make one prompt or group-rule change, run §3.2 again to produce a new
`workflow.json`, then re-run §3.3 (with `workflow_update` instead of
`workflow_create`) and §3.4.

The most common iteration patterns:

- Field extracted as wrong value → tighten `identifiers` and add a
  reusable exclusion in `instructions` ("do not confuse with X")
- Field missing entirely → confirm the value is in the document at
  all via X-Ray (see §3 in `6_known_limitations.md`); if so, broaden
  `identifiers`
- Repeating record over-extracts subtotals → tighten the group-level
  `prompt.instructions` block with explicit IS-NOT examples
- Casing mismatch → add an explicit casing instruction to the field
  ("preserve original casing as printed")

## 4. When to stop

For the harness-guided loop, stop when field-level accuracy is at least 90% or
10 iterations have run. Do not stop early on shape-only success.

For manual production-quality iteration, stop when:

- The accuracy report shows no FAIL rows
- Remaining WARN rows are documented platform-side issues (see
  `6_known_limitations.md`) or convention ambiguities the user has
  decided to accept
- Iteration is not converging — iteration N regresses or fails to
  improve over iteration N-1. See `8_iteration_and_feedback.md` §2 for
  the iteration budget and the non-convergence signal; do not tighten
  prompts further past this point.

Do not stop early because the loop is "good enough" — track every FAIL
or WARN until it is either fixed in the YAML or explicitly accepted
with a note.

## 5. What you keep at the end

- `prompt.yaml` — the durable artifact. Version it, share it, fork it
  as the starting point for related document types.
- `output.json` — the raw GroundX extraction for this specific PDF, when
  `get_extract` is available.
- `output_provenance.json` — confirms which process and document produced the
  raw `output.json`.
- `xray.json` — the raw X-Ray evidence captured by the runner.
- `xray_diagnostic.json` — local reconstruction from X-Ray, written only when
  raw extract is unavailable.
- `xray_reassembly_diagnostic.json` — full SDK readback envelope, including
  final output, workflow debug output, relationship output when present, and
  diagnostics, written with X-Ray reconstruction when available.
- `final_output.json` — local diagnostic/business-logic output, written only
  when produced.
- `business_logic_metadata.json` — run-local final-group metadata used so
  `--resume` applies the same local business logic as the original run.
- `timeout_summary.json` and `timeout_history.json` — written only when local
  polling times out; use the resume command before starting another live run.
- The accuracy report — captures the field-by-field state at the time
  the YAML was finalized.

The intermediate `workflow.json` is reproducible from the YAML at any
time via `compile_workflow.py`; it is not a primary artifact.

## 6. What you don't keep — by design

This skill does not produce a deployable Python project. The reasons
are documented in `7_promote_to_project.md`. If a user explicitly asks
to ship as a project, read that reference first; it explains why the
default deliverable is YAML + JSON, and what the path forward looks
like for production deployments.
