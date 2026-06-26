# 16. Extraction Prompt Writing

This is the first prompt-authoring reference for extraction work. It explains the whole
process first, then routes to the detailed prompt quality and improvement loop guides.

## High-quality extraction process

1. Read the source schema, field catalog, manifest, expected answers, and sample
   documents. Do not write prompts from field names alone.
2. Sketch the final JSON shape and the workflow groups. Keep groups small enough that
   the agent can reason over the fields together.
3. For each field, locate the field in at least one source document before writing the
   prompt. Record the visible label, surrounding context, value shape, and nearby values
   that should not be used.
4. Write field prompts with `description`, `identifiers`, `instructions`, `type`, and
   optional `format`. Use `prompt-quality.md` for the checklist.
5. Put shared record-selection rules in group-level `prompt.instructions`. Do not repeat
   the same rule in every field when the whole group needs it.
6. Compile the YAML and inspect the compiled prompt text before running. The compiled
   prompt is what the model sees.
7. Run extraction, retrieve raw output and X-Ray, then compare against expected answers
   only after source-adjudicating disagreements.
8. Improve by looping one field or one group rule at a time. Use
   `prompt-improvement-loop.md`.

The generic GroundX API prompt guide is useful background for chat prompts, but
extraction prompt work starts here because extraction quality depends on schema shape,
field evidence, X-Ray, scoring, and iteration.

## References

- `prompt-quality.md` defines what a good field, group, and wrapper prompt looks like.
- `prompt-improvement-loop.md` defines how to improve prompts without overfitting or
  losing regressions.
- `2_schema_design.md` defines YAML shape, workflow groups, and source schema rules.
- `3_prompt_pipeline.md` defines custom workflow step behavior and wrapper prompt flow.
- `5_validation.md` defines scoring and source-adjudicated expected-answer mapping.
- `8_iteration_and_feedback.md` defines iteration budgets, non-convergence, and handoff.

## Field prompts

Each field prompt should answer four questions:

1. What value is this? Put that in `description`.
2. Where does it appear? Put representative visible labels in `identifiers`.
3. How should the model choose between similar values? Put that in `instructions`.
4. What shape should the value have? Put that in `type` and `format`.

Good field prompt:

```yaml
event_date:
  workflow_output_key: event_date
  prompt:
    description: Date when the covered event happened.
    identifiers:
      - Event Date
      - Date of Event
      - Occurrence Date
    instructions: Use the date labeled as the covered event or occurrence date. Do not use report date, signature date, received date, or revision date. Return null if no event date is shown.
    format: YYYY-MM-DD
    type: str
```

Avoid vague prompts such as "find the relevant date". Say which date wins and which
nearby dates are wrong.

## Group prompts

Use group-level `prompt.instructions` for rules that apply to every record in a group.

Use it for:

- what counts as one record
- what to exclude
- how to handle subtotals, totals, duplicates, headers, or repeated footers
- rules shared by several fields

Good group prompt:

```yaml
items:
  prompt:
    instructions: |
      Extract one record for each listed item with its own description.
      Do not extract section headers, summary rows, repeated headers, or notes that do not name an item.
```

Do not bury group-wide rules in one field. If the rule affects record selection, put it
on the group.

## Dates, names, codes, and selected values

- Dates: say the exact date role, output format, and which nearby dates are not valid.
- Names: say whether to return the printed name, legal name, short name, or normalized
  value.
- Codes: preserve printed codes exactly unless the user asks for normalization.
- Selected values: when the source uses checkboxes, radio buttons, marked rows, or
  selected states, the selection mark confirms the value. Nearby unselected labels are
  evidence only for locating the field, not for choosing the value.

## Wrapper prompts

Custom extract, reconcile, and QA wrappers should stay thin.

- Extract prompt: source evidence plus field specs in, JSON out.
- Reconcile prompt: candidate values plus source evidence in, best supported value out.
- QA prompt: proposed JSON plus field rules in, corrected JSON or issues out.

Do not put customer business logic only in wrapper prose when it belongs in `prompt.yaml`
metadata or group instructions. YAML should remain the durable source.

## Iteration rules

When a value is wrong:

1. Inspect X-Ray and the per-step output first.
2. Decide whether the problem is field wording, group wording, expected-answer mapping,
   post-extraction business logic, or platform behavior.
3. Change one thing.
4. Recompile and compare the prompt diff before re-running.
5. Run or rescore, then record whether the change improved accuracy or caused a
   regression.

Do not tune prompts to match an expected answer until the source document proves that
expected answer is correct.
