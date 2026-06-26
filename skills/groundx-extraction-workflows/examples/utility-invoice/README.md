# Utility invoice — synthetic custom-step fixture

A small, **fully synthetic** invoice-shaped fixture that proves the custom-step
path end to end and exercises the client-side business-logic metadata. Nothing
here describes a real customer document — the provider, account numbers,
addresses, and amounts are invented for CI.

This is the canonical shipped example: deliberately minimal and CI-safe, used to
prove the compiler and the extension model are domain-agnostic. Real customer
documents and expected answers are supplied out-of-repo and never shipped in the skill.

## Files

| Path | What it is |
|---|---|
| `prompt.yaml` | Schema with `workflow.custom_steps`, `workflow_step:`, `workflow_output_key`, and inline business-logic metadata on each group |
| `data/answer_key.json` | Synthetic expected-answer JSON in the runner output shape `{"statement": {...}, "charges":[...], "meters":[...]}`, with legitimate nulls |
| `business_logic.md` | The linking / dedup / conflict rules "from chat", mapped to the metadata vocabulary |

There is intentionally **no PDF**. CI evals run structurally (compile + validate);
live extraction against a real document runs out-of-repo with credentials.

## The end-to-end loop for this fixture

1. **Compile** — prepare custom workflow metadata and emit workflow JSON. This
   is the CI-safe step (no credentials, no network):

   ```bash
   python ../../templates/compile_workflow.py prompt.yaml
   ```

   `workflow.custom_steps` defines `statement_fields`, `charge_lines`, and
   `meter_lines`; each group points at one step with `workflow_step:`. The
   per-group `unique_attrs`, `match_attrs`, `conflict_attrs`, and `passthrough`
   keys are consumed client-side and never appear in the workflow JSON.

2. **Deploy + ingest + extract** — with credentials, out of repo: deploy the
   workflow with `../../templates/deploy_workflow.py`, then run the full
   ingest → poll → X-Ray → aggregate loop with `../../templates/run_extraction.py`
   (or score a folder of documents with `../../templates/batch_extraction.py`). See
   `../../references/1_extraction_loop.md`.

3. **Apply business logic** — run the metadata primitives over the aggregated
   extract (dedup → passthrough → conflict-surface). See `business_logic.md` and
   `../../templates/business_logic.py`.

4. **Compare** — diff the post-business-logic output against `data/answer_key.json`,
   classifying null-vs-miss. See `../../references/5_validation.md`.

## Why this fixture exists

- Proves custom workflow metadata compiles for invoice-shaped groups.
- Proves the **YAML + metadata** extension axis: a new use case in the invoice
  domain is expressed purely in YAML, with no runner code change.
- Exercises **null-vs-miss** classification via legitimate nulls in expected-answer JSON
  (`budget_plan_name`, and the meterless flat charge's `rate` / `meter_number`).
