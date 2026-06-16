# Customer Extraction Onboarding

Use this reference when a user asks for a new customer extraction pilot, schema kickoff, benchmark, answer-key comparison, or deployment path. This file does not replace the extraction loop; it defines the inputs and readiness checks before the loop starts.

## Intake packet

Collect or confirm:

- document type and business outcome
- target fields, preferably in the customer's spreadsheet or schema
- the owner who can answer field-definition questions
- representative sample documents
- a ground-truth answer key when accuracy will be measured
- the expected output handoff: JSON file, callback, API retrieval, report, or UI review
- whether documents arrive as complete batches or gradually over time
- whether the customer permits storing samples, answer keys, and iteration artifacts

For a shape-only proof, one representative document can be enough. For a serious pilot, prefer 20-100 representative documents when practical. For benchmark-style claims, prefer about 100 clean labeled examples with a trusted answer key. Do not treat a customer-provided answer key as automatically correct; validate obvious mismatches before tightening prompts.

## Desired output shape

Before drafting YAML, ask what JSON the customer wants to consume after
extraction. Write down:

- document-level values
- repeating record lists
- the values that relate records to each other
- fields that must be copied from a parent record to child records
- fields where disagreements should be preserved instead of hidden

Then check whether the desired shape fits the supported relationship model:
dedupe by shared values, match child records to parent records by shared values,
surface conflicts, and passthrough parent values to children. If the customer
needs computed totals, multi-hop matching, unit conversion, conditional
derivation, or document-set-level decisions, record that as a capability gap
before YAML authoring.

Only after the final JSON shape is clear should you assign each real group to a
custom workflow step. If one group is too large, split it into user-approved real
groups or escalate the unsupported grouping need.

## Readiness and batch boundaries

Some workflows cannot know automatically when the document set is complete. If extraction depends on multiple files that arrive over time, make the readiness trigger explicit.

Use a manual readiness trigger when:
- documents arrive through folders, email, SharePoint, ShareFile, S3, or another asynchronous source
- totals or decisions depend on a complete set of related documents
- premature extraction could produce a wrong aggregate result
- the customer has a human operator who already decides when a case/file/package is ready

In those workflows, the app or integration should expose a human action such as "Run extraction", "Mark package ready", or "Process batch now" instead of assuming that every upload should immediately finalize the result.

## Pilot success criteria

Before iteration starts, define:

- target fields and accepted formats
- per-field accuracy bar
- repeating-record accuracy bar, if applicable
- allowed WARN conditions from `5_validation.md`
- maximum iteration budget from `8_iteration_and_feedback.md`
- what happens if the answer key is incomplete or ambiguous
- what artifact is delivered at the end: YAML, workflow JSON, extracted JSON, comparison report, or UI-ready output

Default production-grade bar remains >=95% per-field PASS with WARN rows explicitly accepted. For charges-style repeating records, missing records are usually production blockers unless the customer accepts the exception.

## API handoff

This skill owns YAML, workflow JSON, comparison, and iteration notes. Platform execution still routes to `groundx-api`.

For customer integrations, route to:
- `../../groundx-api/references/02-documents.md` for ingest, polling, extract retrieval, and X-Ray
- `../../groundx-api/references/06-workflows.md` for workflow registration and bucket assignment
- `../../groundx-api/references/08-errors-and-limits.md` for async behavior, callbacks, and ingest limits

If the customer wants push delivery, use the GroundX API callback pattern with `callbackUrl` and `callbackData`; do not invent a custom webhook contract in this skill.

## Do not

- Start schema work from a vague "extract everything" request.
- Promise benchmark accuracy from one or two examples.
- Assume the customer's answer key is correct when the extraction finds plausible extra records.
- Auto-finalize extraction for document sets that require human batch readiness.
- Commit customer documents, answer keys, or private run artifacts unless storage permission is explicit.
