# Insurance claim — non-invoice fixture

A **fully synthetic** fixture that proves the custom-step path is
**domain-agnostic** beyond invoice-shaped output. Its group names — `claim` and
`line_items` — are not invoice group names. Each group uses `workflow_step:` and
the YAML defines `workflow.custom_steps`.

This is the non-invoice smoke gate from the extension model
(`../../references/14_extension_model.md`): if the compiler had silently
re-hardcoded the invoice group names (`statement` / `charges` / `meters`), a YAML
with arbitrary group names would fail to compile. The synthetic expected-answer
JSON then proves the same non-invoice final shape is scoreable.

## Files

| Path | What it is |
|---|---|
| `prompt.yaml` | Two groups with custom steps: `claim` (`kind: instruct`, singleton), `line_items` (`kind: keys`, repeating) |
| `data/answer_key.json` | Synthetic expected-answer JSON in the runner output shape `{"claim": {...}, "line_items": [...]}` |

No PDF, no business-logic metadata — this fixture proves compile, route shape,
and scoring for a non-invoice final object. The invoice-domain fixture
(`../utility-invoice/`) covers null-vs-miss and business-logic metadata.

## The proof

```bash
python ../../templates/compile_workflow.py prompt.yaml > workflow.json
python ../../templates/validate_workflow_json.py workflow.json
python ../../templates/score_extraction.py data/answer_key.json data/answer_key.json
```

Compile exits 0 with `claim` and `line_items` present in the workflow `extract`
block. Validation proves the compiled `customSteps`, `outputRoutes`, and
`leafFields` are structurally usable. The score command exits 0, proving `claim`
singleton fields and `line_items` repeating records are valid runner output
shape. The compiler uses `workflow.custom_steps`, `workflow_step:`, and
`workflow_output_key` to emit `customSteps`, `outputRoutes`, and `leafFields`; see
`../../templates/compile_workflow.py` and `../../references/2_schema_design.md`.
