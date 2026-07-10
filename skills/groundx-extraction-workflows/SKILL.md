---
name: groundx-extraction-workflows
version: 0.2.0
description: >
  Use this skill when an agent needs to extract structured data from a PDF
  or other document using GroundX. Triggers include drafting or iterating an
  extraction YAML schema, compiling workflow JSON, running an extraction,
  comparing output to reviewer-provided expected answers, debugging missing or wrong fields, and
  planning a serious extraction pilot. Platform API operations delegate to
  `groundx-api`.
---

# GroundX Extraction Workflows

This skill is schema-first: the durable artifact is a YAML schema;
`compile_workflow.py` translates it into workflow JSON; `deploy_workflow.py`
deploys a finished YAML through the GroundX Python SDK; `run_extraction.py`
runs the full ingest/poll/X-Ray/extract loop and can resume a timed-out local
poll with `--resume --out <run-dir>`. Interactive platform execution delegates
to `groundx-api`.

Before live ingest, estimate request fanout from expected pages, chunks per
page, and chunk-level custom steps. Pseudo groups reduce prompt load but pseudo
groups at `level: chunk` still multiply requests. For large statement-style
documents, prefer `workflow.section_strategy: page` with `level: section` when
the chunk estimate approaches the request cap.

For public extraction documentation and installed-agent runtime guidance, read
`references/public-docs.md` first. Public docs should use the GroundX SDK path,
including `client.ingest(...)`, and keep harness/compiler internals out unless
the user explicitly asks for SDK internals.

## Routing Contract

- **Role:** `artifact`.
- **First-entry intents:** schema-first extraction, extraction YAML, extraction
  workflow authoring, compile-to-workflow JSON, field-accuracy iteration, pilot
  acceptance criteria, or comparison to expected answers.
- **Deferrals:** interactive workflow registration, bucket attachment, document
  ingest, polling, and extraction retrieval route to `groundx-api`; on-prem
  deployment questions route to `groundx-on-prem`; architecture questions route to
  `groundx-architecture`.
- **Before producing output:** read this skill's reference index and schema/compiler
  guidance before drafting YAML or workflow JSON.
- **Misuse cases:** do not put real API keys in generated files, examples, logs,
  prompts, or transcripts. Use `deploy_workflow.py` for local deploy-only SDK
  execution, `groundx-api` MCP for interactive agent operations, and
  `run_extraction.py` for deploy + ingest + poll + X-Ray + extract.

## Fast Path

1. Read `references/README.md`.
2. For the broad ordered workflow path, read `references/workflow-how-to.md`.
3. For public extraction docs, read `references/public-docs.md`.
4. For a new customer or serious pilot, read `references/customer-onboarding.md` and
   optionally `references/openspec-pilots.md`.
5. Draft or revise `prompt.yaml` using `references/16_prompt_writing.md`,
   `references/prompt-quality.md`, `references/prompt-improvement-loop.md`,
   `references/2_schema_design.md`, and `references/3_prompt_pipeline.md`.
6. If the domain needs custom extract/reconcile/QA prompt wrappers, read
   `references/prompt-manager.md` and use `templates/prompt_manager.py` as the
   minimal today-path manager.
7. Compile the YAML into `workflow.json` with `templates/compile_workflow.py`.
8. Estimate request fanout with `templates/estimate_workflow_requests.py` or
   live-run preflight before ingest.
9. For a finished YAML, read `references/deploy.md`, then use
   `templates/deploy_workflow.py` to deploy the workflow through the GroundX Python SDK.
   For a full local run, use
   `templates/run_extraction.py`. For interactive platform execution, route to
   `groundx-api`.
10. Score against expected answers: `templates/score_extraction.py` for one document, or
   `templates/batch_extraction.py` to ingest + score a folder live. To re-score a captured
   run **offline (no re-ingest)** — after fixing expected-answer mappings or to score on
   another machine — use `templates/batch_score.py <run_dir> --keys-dir <expected-answers>`.
   If expected answers arrive as spreadsheets, documents, text files, PDFs, or
   human-review notes, map them into runner-shaped JSON before scoring.
11. Iterate one field at a time with `references/prompt-improvement-loop.md`; inspect
   X-Ray before tightening prompts when accuracy stalls or a field is wrong.

## What This Skill Produces

This skill produces `prompt.yaml`, compiled `workflow.json`, extracted JSON after
`groundx-api` execution, deploy metadata from `templates/deploy_workflow.py`, an
accuracy report when expected answers exist, and the minimal
`templates/prompt_manager.py` manager shape when custom prompt wrappers are needed. A
full deployable project scaffold is not part of the default deliverable.

## Pre-return Checklist

- [ ] YAML remains the durable source of truth.
- [ ] Workflow JSON is reproducible from YAML.
- [ ] Finished-YAML deploy uses `deploy_workflow.py`; interactive platform execution
      delegates to `groundx-api`.
- [ ] No real GroundX API key appears in any artifact.
- [ ] Group decomposition is explicit.
- [ ] Request fanout is estimated from pages, chunks per page, custom steps, and
      pseudo groups before live ingest; large statement-style workflows consider
      `workflow.section_strategy: page`.
- [ ] Field fixes identify the specific YAML line or field to change.
- [ ] Prompt edits follow `references/16_prompt_writing.md`,
      `references/prompt-quality.md`, and `references/prompt-improvement-loop.md`.
- [ ] X-Ray was inspected before tightening prompts when accuracy stalls.
