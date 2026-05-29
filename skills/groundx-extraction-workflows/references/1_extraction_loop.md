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
                            │ output.json  │
                            └──────┬───────┘
                                   │ python compare.py
                                   ▼
                          pass/fail/warn report
```

The user edits `prompt.yaml`. Everything downstream is mechanical:
`compile_workflow.py` produces the workflow JSON, `groundx-api`
operations register and run it, `compare.py` evaluates accuracy.

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
7. `compare.py` — copied from
   `skills/groundx-extraction-workflows/templates/compare.py`
8. `requirements.txt` — copied from
   `skills/groundx-extraction-workflows/templates/requirements.txt`
9. The input PDF (named anything; pass the path as needed)
10. A ground truth file: CSV (preferred for v1) or JSON

A throwaway working directory under `/tmp` is fine for one-shot
extractions. A persistent directory (e.g.
`~/extractions/<customer>/`) is fine for ongoing iteration.

```bash
pip install -r requirements.txt
```

## 3. The loop

### 3.1 Draft the YAML

Read §2 in `2_schema_design.md` for group decomposition and field
anatomy. Author the YAML based on:

- The fields the user wants to extract (or, if a ground truth is
  provided, the keys in the ground truth)
- One worked example to look at the document and identify each field's
  visual identifiers and edge cases
- The two-group convention: `statement:` for per-document fields,
  `charges:` for repeating records

If the document type does not fit either shape, see "When you have
neither" in `2_schema_design.md`.

### 3.2 Compile to workflow JSON

```bash
python compile_workflow.py prompt.yaml > workflow.json
```

`compile_workflow.py` is offline — it does not call any GroundX API.
It loads the YAML, renders the field-spec text, and emits the
workflow JSON in the exact shape the GroundX workflow API accepts.

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

Read `deploy.md` before running it. The short version: use `--bucket-id`
for an existing bucket ID, `--bucket-name` for an exact existing bucket-name
lookup, and `--create-bucket-name` when the command should create a new bucket.
Use `--dry-run` first when you want compile/validation and planned actions
without a live API call.

**Full local run:** when you need deploy + ingest + poll + X-Ray +
extract output, use `run_extraction.py`.

**Interactive agent path:** when an agent is operating inside Claude or
Codex and GroundX MCP tools are visible, follow the `groundx-api`
MCP-first flow: check for GroundX MCP tools, tell the user to connect
the GroundX MCP connector to GroundX if they are missing, call
`groundx_account_context` when connected, and use the GroundX Python SDK
for local script execution. The extraction skill remains the schema
authoring reference; `groundx-api` remains the operation-semantics
reference.

The manual operation loop is:

1. **Create or update the workflow.** POST `workflow.json` via the
   `workflow_create` MCP tool or the `workflows.create()` SDK call. The
   response includes the `workflowId`.
2. **Attach the workflow to a bucket.** Either an existing bucket or a
   new one. Use `workflow_add_to_id` MCP tool or the equivalent SDK
   call.
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
# After running steps 1-5 via groundx-api, you have output.json
```

### 3.4 Compare to ground truth

```bash
python compare.py output.json ground_truth.csv
```

The comparator emits a structured report: PASS / FAIL / WARN per
field, with the expected and extracted values for any non-PASS row.
See §2 in `5_validation.md` for what each verdict means and how the
comparison logic treats casing, dates, floats, and arrays.

### 3.5 Iterate

For every FAIL or WARN, identify the YAML field that produced it. The
map is direct: each field's YAML key becomes the JSON key in the
output. Tighten the field's `instructions` block, save the YAML, run
§3.2 again to produce a new `workflow.json`, then re-run §3.3 (with
`workflow_update` instead of `workflow_create`) and §3.4.

The most common iteration patterns:

- Field extracted as wrong value → tighten `identifiers` and add a
  negative example in `instructions` ("do not confuse with X")
- Field missing entirely → confirm the value is in the document at
  all via X-Ray (see §3 in `6_known_limitations.md`); if so, broaden
  `identifiers`
- Repeating record over-extracts subtotals → tighten the group-level
  `prompt.instructions` block on the `charges` group with explicit
  IS-NOT examples
- Casing mismatch → add an explicit casing instruction to the field
  ("preserve original casing as printed")

## 4. When to stop

Stop when:

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
- `output.json` — the extraction for this specific PDF.
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
