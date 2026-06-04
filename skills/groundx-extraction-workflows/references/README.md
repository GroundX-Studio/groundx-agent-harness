# GroundX Extraction Workflows Reference Index

Use this index when the work involves drafting or iterating an extraction YAML schema,
compiling YAML to GroundX workflow JSON, running an extraction against a PDF or other
document, comparing extraction output to a ground-truth answer key, debugging a field,
or planning a serious extraction pilot.

## Fast Path

1. Read `../SKILL.md`.
2. For a new pilot, read `customer-onboarding.md`; for durable requirements and
   acceptance criteria, also read `openspec-pilots.md`.
3. Draft or revise YAML with `2_schema_design.md` and `3_prompt_pipeline.md`.
4. Compile with `templates/compile_workflow.py`.
5. Use `deploy.md` and `templates/deploy_workflow.py` for deploy-only local SDK
   execution, or `templates/run_extraction.py` for a full local run.
6. Route interactive platform execution to `groundx-api`.
7. Compare output with `templates/score_extraction.py`.
8. Iterate one field at a time.

## What To Use

| Need | Read |
| --- | --- |
| Public or customer-facing extraction docs | `public-docs.md` |
| End-to-end loop: draft YAML -> compile -> deploy or run -> compare -> iterate | `1_extraction_loop.md` |
| New customer pilot, sample-set requirements, answer-key readiness, API handoff expectations | `customer-onboarding.md`, then `1_extraction_loop.md` |
| Optional OpenSpec structure for serious pilots | `openspec-pilots.md` |
| Authoring or revising YAML schema | `2_schema_design.md` |
| Choosing workflow slots and preserving RAG while extracting | `3_prompt_pipeline.md` |
| Wrapping YAML with custom extract/reconcile/QA prompt modules and managing prompt iterations today | `prompt-manager.md` |
| Finished-YAML deployment decision: MCP vs deploy-only local script vs full local run | `deploy.md` |
| Modifying compiler, deploy, or runner behavior | `4_sdk_integration.md` |
| Building or reading a comparison report; field-level scoring and miss types | `5_validation.md` |
| A repeating group (charges, meters, line items) scores low: prompt patterns + field-level iteration loop | `15_repeating_groups.md` |
| Platform-locked field names and escalation | `6_known_limitations.md` |
| Deployable project path | `7_promote_to_project.md` |
| Iteration budget and non-convergence signals | `8_iteration_and_feedback.md` |
| Skill testing methodology | `9_testing_methodology.md` |
| Diagnosing why extraction failed or regressed | `10_debugging_methodology.md` |

## Default Decisions

Use this skill by default for structured-data extraction tasks on documents. For
serious pilots, define target fields, representative samples, answer-key quality,
accepted formats, comparison thresholds, and output handoff before iteration starts.

For public or customer-facing extraction docs, read `public-docs.md` first. Use
the GroundX SDK path with `client.ingest(...)`, show the JSON the customer gets
back, and keep harness/compiler internals out unless the user explicitly asks
for SDK internals.

Keep customer documents, answer keys, private notes, and run outputs out of committed
artifacts unless the customer explicitly approves sharing.

When a customer or sample repo already has a `manager.py`, `simple.yaml`, and separate
extract/reconcile/QA prompt modules, use `prompt-manager.md` instead of forcing those
wrappers into inline compiler functions. The today path is a small manager adapter
(`templates/prompt_manager.py`) plus optional `EXTRACT_WRAPPER_MODULE` support in
`compile_workflow.py`; the future path is a single YAML-driven
`groundx-python/extract` abstraction.

Use `deploy.md` and `deploy_workflow.py` when a finished YAML only needs workflow create/update and
attachment through the GroundX Python SDK. Use `run_extraction.py` when you need ingest,
polling, X-Ray, and extract retrieval in one local command.
