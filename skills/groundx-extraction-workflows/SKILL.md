---
name: groundx-extraction-workflows
version: 0.1.5
description: >
  Use this skill when an agent needs to extract structured data from a PDF
  or other document using GroundX. Triggers include drafting or iterating an
  extraction YAML schema, compiling workflow JSON, running an extraction,
  comparing output to ground truth, debugging missing or wrong fields, and
  planning a serious extraction pilot. Platform API operations delegate to
  `groundx-api`.
---

# GroundX Extraction Workflows

This skill is schema-first: the durable artifact is a YAML schema;
`compile_workflow.py` translates it into workflow JSON; platform execution
delegates to `groundx-api`.

## Routing Contract

- **Role:** `artifact`.
- **First-entry intents:** schema-first extraction, extraction YAML, extraction
  workflow authoring, compile-to-workflow JSON, field-accuracy iteration, pilot
  acceptance criteria, or comparison to ground truth.
- **Deferrals:** workflow registration, bucket attachment, document ingest, polling,
  and extraction retrieval route to `groundx-api`; deployment questions route to
  `groundx-on-prem`; architecture questions route to `groundx-architecture`.
- **Before producing output:** read this skill's reference index and schema/compiler
  guidance before drafting YAML or workflow JSON.
- **Misuse cases:** do not put real API keys in generated files, examples, logs, or
  transcripts; do not register workflows without routing to `groundx-api`.

## Fast Path

1. Read `references/README.md`.
2. For a new customer or serious pilot, read `references/customer-onboarding.md` and
   optionally `references/openspec-pilots.md`.
3. Draft or revise `prompt.yaml` using `references/2_schema_design.md` and
   `references/3_prompt_pipeline.md`.
4. Compile the YAML into `workflow.json` with `templates/compile_workflow.py`.
5. Delegate workflow registration, bucket attachment, ingest, polling, and extract
   retrieval to `groundx-api`.
6. Compare output with `templates/compare.py` when ground truth exists.
7. Iterate one field at a time; inspect X-Ray before tightening prompts when accuracy
   stalls or a field is wrong.

## What This Skill Produces

This skill produces `prompt.yaml`, compiled `workflow.json`, extracted JSON after
`groundx-api` execution, and an accuracy report when ground truth exists. A deployable
project scaffold is not part of the default deliverable.

## Pre-return Checklist

- [ ] YAML remains the durable source of truth.
- [ ] Workflow JSON is reproducible from YAML.
- [ ] Platform execution delegates to `groundx-api`.
- [ ] No real GroundX API key appears in any artifact.
- [ ] Group decomposition is explicit.
- [ ] Field fixes identify the specific YAML line or field to change.
- [ ] X-Ray was inspected before tightening prompts when accuracy stalls.
