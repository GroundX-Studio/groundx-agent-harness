# Insurance claim — non-invoice fixture

A **fully synthetic** fixture that proves the custom-step path is
**domain-agnostic** beyond invoice-shaped output. Its group names — `claim` and
`line_items` — are not invoice group names. Each group uses `workflow_step:` and
the YAML defines `workflow.custom_steps`.

This is the non-invoice smoke gate from the extension model
(`../../references/14_extension_model.md`): if the server compiler had silently
re-hardcoded the invoice group names (`statement` / `charges` / `meters`), a YAML
with arbitrary group names would fail server validation. The synthetic expected-answer
JSON then proves the same non-invoice final shape is scoreable.

## Files

| Path | What it is |
|---|---|
| `prompt.yaml` | Two groups with custom steps: `claim` (`kind: instruct`, singleton), `line_items` (`kind: keys`, repeating) |
| `data/answer_key.json` | Synthetic expected-answer JSON in the runner output shape `{"claim": {...}, "line_items": [...]}` |

No PDF, no business-logic metadata. This fixture proves topology, route shape,
and scoring for a non-invoice final object. The invoice-domain fixture
(`../utility-invoice/`) covers null-vs-miss and business-logic metadata.

## The proof

This command writes a temporary offline request estimate. Before running it, follow
[`local-artifact-closeout.md`](../../references/local-artifact-closeout.md), initialize a
planned run or choose one dedicated ad-hoc root, and export its absolute path as `RUN_ROOT`.

```bash
python ../../templates/estimate_workflow_requests.py --workflow-yaml prompt.yaml --json > "$RUN_ROOT/request-estimate.json"
python ../../templates/score_extraction.py data/answer_key.json data/answer_key.json
```

The estimator reads authored custom steps without compiling the workflow. It is
non-authoritative: the GroundX API is the only workflow compiler, and
registration submits `prompt.yaml` itself after
`gx.workflows.validate(name=..., yaml=...)` passes (that check needs
credentials, so it runs in the live lane, not CI). The score command exits 0,
proving `claim` singleton fields and `line_items` repeating records are valid
runner output shape. The YAML uses `workflow.custom_steps`, `workflow_step:`,
and `workflow_output_key`; see `../../references/2_schema_design.md`.
Delete the topology model with the settled run root; retain only the bounded
summary and any explicitly approved reviewed handoff.
