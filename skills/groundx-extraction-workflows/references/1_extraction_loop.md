# 1. The extraction loop

Before any command here creates local output, read [`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must initialize and use its exact absolute run root. Ad-hoc work uses one dedicated root. Settle or hand off useful results, delete raw evidence, verify absence, and report what remains.

This is the default end-to-end loop the skill walks through. It is
single-file at the YAML layer, delegates execution to the GroundX API
(via the `groundx-api` skill), and is reproducible: the same source YAML is
validated and registered by the same server compiler, then applied to the same
document.

## 1. Overview

```
┌─────────────┐   validate   ┌──────────────┐
│ prompt.yaml │─────────────►│ GroundX API  │
└─────┬───────┘              └──────┬───────┘
      │                             │
      │                             │ create from YAML + attach to bucket
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

The user edits `prompt.yaml`. Everything downstream is mechanical: the
GroundX API compiles the YAML server-side at create time, `groundx-api`
operations register and run it, `score_extraction.py` evaluates accuracy.

## 2. Setup

Before the loop runs, the working directory must have:

1. `prompt.yaml` — copied from
   `skills/groundx-extraction-workflows/templates/prompt.yaml` and edited for the
   target document type
2. `.env` — copied from `skills/groundx-extraction-workflows/templates/.env.sample`
   and populated with either `GROUNDX_API_KEY`, or both `PARTNER_API_KEY` and
   `CUSTOMER_USERNAME` for a delegated customer-owned run. Do not mix modes.
3. `_workflow_source.py` — copied from
   `skills/groundx-extraction-workflows/templates/_workflow_source.py`
   (small source reader only; never validates or compiles)
4. `deploy_workflow.py` — copied from
   `skills/groundx-extraction-workflows/templates/deploy_workflow.py` when the
   finished YAML needs workflow create/update and attachment
5. `run_extraction.py` — copied from
   `skills/groundx-extraction-workflows/templates/run_extraction.py` when the
   same command should also ingest, poll, capture X-Ray, and retrieve extract
6. `score_extraction.py` — copied from
   `skills/groundx-extraction-workflows/templates/score_extraction.py`
7. `run_extraction_loop.py` — copied from
   `skills/groundx-extraction-workflows/templates/run_extraction_loop.py` when
   the work is PDF plus desired schema plus expected answers and should iterate
   up to 10 times or until accuracy is at least 90%
8. `requirements.txt` — copied from
   `skills/groundx-extraction-workflows/templates/requirements.txt`
9. The input PDF (named anything; pass the path as needed)
10. Expected answers for scoring. If they are already runner-shaped JSON, use
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

### 3.2 Validate with the server

```python
gx.workflows.validate(name=workflow_name, yaml=yaml_text)
```

The GroundX API is the only workflow compiler. Submit the source YAML
(`workflows.create(name=..., yaml=...)`) and let the server compile;
`workflows.validate` on the same YAML is the only preflight that predicts
`create()` and must pass before workflow create/update, MCP registration, or
ingest.

The server workflow readback saved as `workflow.json` is a diagnostic artifact
for this run. Diff it across iterations, but do not submit it as authoring input
or treat it as proof of the rendered LLM request.

### 3.3 Deploy or run the workflow

Use the smallest path that matches the task.

**Deploy-only:** when the YAML is finished and you only need to register
or attach the workflow, use the local SDK deploy command:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out "$RUN_ROOT/deploy" \
  --workflow-name customer-workflow-v1 \
  --create-bucket-name customer-bucket-v1
```

`deploy_workflow.py` asks the server to validate the source YAML, then creates
or updates the workflow with that same YAML through the GroundX Python SDK. It can
attach it to a bucket or the account default. It writes `workflow.json`,
`deploy.json`, `workflow_id.txt`, and `bucket_id.txt` when applicable.
It is deploy-only; it does not ingest files, poll status, capture X-Ray,
or retrieve extract output.

This uses the same source-YAML API path as product upload. Record the actual
entrypoint when evidence must distinguish SDK, MCP, or product behavior.

Read `deploy.md` before running it. The short version: use `--bucket-id`
for an existing bucket ID, `--bucket-name` for an exact existing bucket-name
lookup, and `--create-bucket-name` when the command should create a new bucket.
Use `--dry-run` first for local parsing, fanout estimation, and planned actions.
It makes no live API call and does not prove server acceptance.

**Full local run:** when you need prod deploy + ingest + poll + X-Ray +
extract output, use `run_extraction.py`. Dev structured extraction does not
currently work; do not run this path against dev unless an operator explicitly
confirms it is available. The runner writes `output.json` only for the
raw GroundX `get_extract` payload. If raw extract is unavailable, it preserves
`xray.json` without synthesizing output. Add
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
when present. It does not validate, create, update, or re-read source YAML.

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
  --out "$RUN_ROOT/loop" \
  --iteration-schema-dir iterations/
```

If the score is below 90%, inspect the PDF, X-Ray, raw extraction, score report,
and the server workflow readback diff. Make one prompt or group-rule change,
save it as `iterations/prompt.iteration-02.yaml` or `iterations/iteration-02.yaml`,
and continue. The runner reports `blocked` instead of retrying the same YAML
when no next revision is available.

**Interactive agent path:** when an agent is operating inside Claude or
Codex, follow `groundx-api` operation semantics with the selected
environment's `GROUNDX_API_KEY`. A partner acting for a customer instead uses
`PARTNER_API_KEY` plus `CUSTOMER_USERNAME`; the actor is privileged, while the
selected customer owns every workflow relationship and document operation. Use the GroundX Python SDK by default.
Full live extraction should target prod unless an operator confirms dev
extraction is available. For dev non-extraction API/debug calls, set
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`; for prod, leave it unset.
GroundX MCP is optional and prod-only. The extraction skill remains the schema
authoring reference; `groundx-api` remains the operation-semantics reference.

The manual operation loop is:

1. **Create or update the workflow.** Submit the authored YAML via the
   `workflows.create(name=..., yaml=...)` SDK call. In prod sessions where MCP
   is already connected, `workflow_create` with the same source YAML is also
   acceptable. The response includes the `workflowId`.
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

## 5. What remains after closeout

During the run, keep `output.json`, provenance, X-Ray, diagnostics,
`final_output.json`, business-logic metadata, timeout history, comparison reports, and
the reproducible `workflow.json` only below the initialized run root. They are temporary
evidence, not durable plan output.

At closeout:

- hand off the reviewed `prompt.yaml` to a named, nonignored tracked location when it is
  the accepted deliverable;
- hand off a reviewed final JSON or accuracy decision only when the user requested it and
  selected an approved destination;
- retain bounded outcomes, provenance, the first failing stage, cleanup counts, and an
  aggregate digest in the lifecycle-only summary and tracked receipt; and
- delete the raw extraction, X-Ray, prompt/model response, diagnostics, timeout history,
  intermediate workflow, and comparison bundle with the exact run root.

Do not preserve raw evidence in another broad ignored directory. Follow
[`local-artifact-closeout.md`](./local-artifact-closeout.md), verify the run root is absent,
and report every durable handoff and anything intentionally left open.

## 6. What you don't keep — by design

This skill does not produce a deployable Python project. The reasons
are documented in `7_promote_to_project.md`. If a user explicitly asks
to ship as a project, read that reference first; it explains why the
default deliverable is YAML + JSON, and what the path forward looks
like for production deployments.
