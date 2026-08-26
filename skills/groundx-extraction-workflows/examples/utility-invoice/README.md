# Utility invoice — synthetic custom-step fixture

A small, **fully synthetic** invoice-shaped fixture that proves the custom-step
path end to end and exercises hosted identity/relationship metadata. Nothing
here describes a real customer document — the provider, account numbers,
addresses, and amounts are invented for CI.

This is the canonical shipped example: deliberately minimal and CI-safe, used to
prove the server authoring contract and extension model are domain-agnostic. Real customer
documents and expected answers are supplied out-of-repo and never shipped in the skill.

## Files

| Path | What it is |
|---|---|
| `prompt.yaml` | Schema with `workflow.custom_steps`, `workflow_step:`, `workflow_output_key`, and inline business-logic metadata on each group |
| `data/answer_key.json` | Synthetic expected-answer JSON in the runner output shape `{"statement": {...}, "charges":[...], "meters":[...]}`, with legitimate nulls |
| `business_logic.md` | The linking / dedup / conflict rules "from chat", mapped to the metadata vocabulary |

There is intentionally **no PDF**. CI evals run offline source and scoring checks;
live extraction against a real document runs out-of-repo with credentials.

## The end-to-end loop for this fixture

1. **Author** — the YAML is the deployable artifact; the GroundX API
   compiles it server-side at create time. The CI-safe offline check is the
   request-fanout estimate (no credentials, no network):

   ```bash
   python ../../templates/estimate_workflow_requests.py --workflow-yaml prompt.yaml --json
   ```

   `workflow.custom_steps` defines `statement_fields`, `charge_lines`, and
   `meter_lines`; each group points at one step with `workflow_step:`. The
   per-group `unique_attrs`, `match_attrs`, `conflict_attrs`, and `passthrough`
   keys capture product intent. Cashbot compiles and dispatches the metadata;
   GroundX Python owns generic identity, reassembly, and relationship behavior;
   each hosted extraction service owns only its service-specific policy.

2. **Deploy + ingest + extract** — with credentials, out of repo: deploy the
   workflow with `../../templates/deploy_workflow.py`, then run the full
   ingest → poll → X-Ray → aggregate loop with `../../templates/run_extraction.py`
   (or score a folder of documents with `../../templates/batch_extraction.py`). See
   `../../references/1_extraction_loop.md`.

3. **Verify hosted behavior** — inspect raw `get_extract` for the supported
   identity, relationship, propagation, and conflict behavior declared in YAML.
   Harness never constructs a replacement result. See `business_logic.md`.

4. **Compare** — diff raw hosted output against `data/answer_key.json`,
   classifying null-vs-miss. See `../../references/5_validation.md`.

## Why this fixture exists

- Proves custom workflow metadata compiles for invoice-shaped groups.
- Proves the **YAML + metadata** extension axis: a new use case in the invoice
  domain is expressed in YAML, while missing hosted behavior belongs to the
  owning product repository rather than Harness runner code.
- Exercises **null-vs-miss** classification via legitimate nulls in expected-answer JSON
  (`budget_plan_name`, and the meterless flat charge's `rate` / `meter_number`).
