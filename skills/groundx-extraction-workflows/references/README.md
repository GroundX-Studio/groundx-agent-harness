# GroundX Extraction Workflows Reference Index

Before any command here creates local output, read [`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must initialize and use its exact absolute run root. Ad-hoc work uses one dedicated root. Settle or hand off useful results, delete raw evidence, verify absence, and report what remains.

Use this index when the work involves drafting or iterating an extraction YAML schema,
compiling YAML to GroundX workflow JSON, running an extraction against a PDF or other
document, comparing extraction output to reviewer-provided expected answers, debugging
a field, or planning a serious extraction pilot.

## Fast Path

1. Read `../SKILL.md`.
2. For a new pilot, read `customer-onboarding.md`; for durable requirements and
   acceptance criteria, also read `openspec-pilots.md`.
3. For the broad ordered workflow path, read `workflow-how-to.md`.
4. Draft or revise YAML with `16_prompt_writing.md`, `prompt-quality.md`,
   `prompt-improvement-loop.md`, `2_schema_design.md`, and `3_prompt_pipeline.md`.
5. Validate with the server (`gx.workflows.validate`).
6. Use `deploy.md` and `templates/deploy_workflow.py` for deploy-only local SDK
   execution, or `templates/run_extraction.py` for a full local run.
7. Route interactive platform execution to `groundx-api`.
8. Compare output with `templates/score_extraction.py`.
9. Iterate one field at a time.

## What To Use

| Need | Read |
| --- | --- |
| Public extraction docs and installed-agent runtime guidance | `public-docs.md` |
| Broad ordered workflow path: intake -> final schema -> prompt writing -> workflow groups -> server validation -> deploy or run -> compare -> iterate | `workflow-how-to.md` |
| Detailed extraction loop: draft YAML -> server validation -> deploy or run -> compare -> iterate | `1_extraction_loop.md` |
| New customer pilot, sample-set requirements, expected-answer readiness, API handoff expectations | `customer-onboarding.md`, then `1_extraction_loop.md` |
| Optional OpenSpec structure for serious pilots | `openspec-pilots.md` |
| Authoring or revising YAML schema | `16_prompt_writing.md`, `prompt-quality.md`, `2_schema_design.md` |
| Improving prompts after misses or reviewer feedback | `prompt-improvement-loop.md`, then `16_prompt_writing.md` |
| Choosing custom workflow steps and preserving RAG while extracting | `3_prompt_pipeline.md` |
| Estimating request fanout before live ingest; choosing chunk versus page-section execution | `2_schema_design.md`, `3_prompt_pipeline.md`, `templates/estimate_workflow_requests.py` |
| Wrapping YAML with custom extract/reconcile/QA prompt modules and managing prompt iterations today | `prompt-manager.md` |
| Finished-YAML deployment decision: MCP vs deploy-only local script vs full local run | `deploy.md` |
| Modifying compiler, deploy, or runner behavior | `4_sdk_integration.md` |
| Building or reading a comparison report; field-level scoring, miss types, and mapping non-JSON expected answers before scoring | `5_validation.md` |
| A repeating group (charges, meters, line items) scores low: prompt patterns + field-level iteration loop | `15_repeating_groups.md` |
| Platform-locked field names and escalation | `6_known_limitations.md` |
| Deployable project path | `7_promote_to_project.md` |
| Iteration budget and non-convergence signals | `8_iteration_and_feedback.md` |
| Skill testing methodology | `9_testing_methodology.md` |
| Diagnosing why extraction failed or regressed | `10_debugging_methodology.md` |
| Demo request with a missing source document or expected answers | `13_customer_intake.md`; never invent schema, results, or accuracy |

## Default Decisions

Use this skill by default for structured-data extraction tasks on documents. For
serious pilots, define target fields, representative samples, expected-answer quality
and format, comparison thresholds, and output handoff before iteration starts.

For public extraction docs, read `public-docs.md` first. Use
the GroundX SDK path with `client.ingest(...)`, show the JSON the customer gets
back, and keep harness/compiler internals out unless the user explicitly asks
for SDK internals.

Keep customer documents, expected answers, private notes, and run outputs out of committed
artifacts unless the customer explicitly approves sharing.

Estimate request fanout before live ingest. Use expected pages, chunks per
page, and custom step counts: `pages * chunks per page * chunk-level custom
steps`. Pseudo groups reduce field and prompt load, but pseudo groups at
`level: chunk` still multiply requests. For large statement-style documents,
prefer `workflow.section_strategy: page` plus `level: section` when chunk
fanout approaches the 2000 request cap.

Use `16_prompt_writing.md`, `prompt-quality.md`, and `prompt-improvement-loop.md`
before drafting or tightening prompts. The skill should teach the full process first:
source evidence, final shape, prompt writing, server validation, run, source-adjudicated scoring,
one-change prompt loops, and regression checks.

When a customer or sample repo already has a `manager.py`, `simple.yaml`, and separate
extract/reconcile/QA prompt modules, use `prompt-manager.md` instead of forcing those
wrappers into inline functions. The supported path is a small manager adapter
(`templates/prompt_manager.py`) plus authored YAML submitted to the server.

Use `deploy.md` and `deploy_workflow.py` when a finished YAML only needs workflow create/update and
attachment through the GroundX Python SDK. Use `run_extraction.py` when you need ingest,
polling, X-Ray, and extract retrieval in one local command. If local polling times out,
resume the same run with `python run_extraction.py --resume --out <run-dir>` before
redeploying or re-ingesting.
