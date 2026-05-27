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
5. Route platform execution to `groundx-api`.
6. Compare output with `templates/compare.py`.
7. Iterate one field at a time.

## What To Use

| Need | Read |
| --- | --- |
| End-to-end loop: draft YAML -> compile -> run -> compare -> iterate | `1_extraction_loop.md` |
| New customer pilot, sample-set requirements, answer-key readiness, API handoff expectations | `customer-onboarding.md`, then `1_extraction_loop.md` |
| Optional OpenSpec structure for serious pilots | `openspec-pilots.md` |
| Authoring or revising YAML schema | `2_schema_design.md` |
| Choosing workflow slots and preserving RAG while extracting | `3_prompt_pipeline.md` |
| Modifying compiler or runner behavior | `4_sdk_integration.md` |
| Building or reading a comparison report | `5_validation.md` |
| Platform-locked field names and escalation | `6_known_limitations.md` |
| Deployable project path | `7_promote_to_project.md` |
| Iteration budget and non-convergence signals | `8_iteration_and_feedback.md` |
| Skill testing methodology | `9_testing_methodology.md` |
| Diagnosing why extraction failed or regressed | `10_debugging_methodology.md` |

## Default Decisions

Use this skill by default for structured-data extraction tasks on documents. For
serious pilots, define target fields, representative samples, answer-key quality,
accepted formats, comparison thresholds, and output handoff before iteration starts.

Keep customer documents, answer keys, private notes, and run outputs out of committed
artifacts unless the customer explicitly approves sharing.
