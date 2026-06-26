# Prompt Quality

Use this guide before writing or tightening extraction prompts. A good prompt makes the
agent choose the right source value across many document layouts, not just the current
sample.

## Good Prompt Checklist

A good extraction prompt is:

- **source-grounded**: it tells the agent what visible source evidence proves the value.
- **schema-grounded**: it matches the field definition, output type, and final JSON
  shape.
- **behavior-changing**: it gives a rule that changes a decision the agent could get
  wrong.
- **general**: it names reusable evidence patterns, not one sample's page layout.
- **short**: it says enough to choose correctly without hiding the rule in prose.

## Field prompt parts

Use every part for a reason:

- `description`: the business meaning of the field, not a copy of the field name.
- `identifiers`: representative identifiers and labels that help locate the field.
  Include labels with the same meaning, not every nearby phrase.
- `instructions`: decision rules, exclusions, null rules, and normalization rules.
- `type`: the JSON value shape.
- `format`: required formatting such as `YYYY-MM-DD`, currency, percentage, enum, or
  JSON object string.

## Representative identifiers

Identifiers should help find the field when labels vary. Good identifiers describe the
meaning of the label, not only the exact words seen once.

Example:

```yaml
identifiers:
  - Effective Date
  - Start Date
  - Date coverage begins
```

This tells the agent to look for labels that mean "the date this thing starts". Do not
add unrelated nearby labels just because they appear on the same page.

## Output shape

The prompt must state the output shape when ambiguity exists:

- date format
- number vs string
- boolean vs selected label
- enum choice
- JSON object string with `value` and `_raw_text`
- null when the source does not support an answer

For enum fields, list the valid choices in the field instructions. If the source text
does not exactly match an enum value and an `Other` choice exists, return `Other` and
put the printed source value in `_raw_text`.

## Selected values

When a document uses checkboxes, radio buttons, marked rows, or selected states, the
selected checkbox or mark confirms the value. Labels near an unselected option help
locate the field but do not prove that option is the answer.

General rule:

```text
Use the value associated with the selected or marked option. Do not choose a value only
because its label appears nearby.
```

## Group prompts

Use group-level `prompt.instructions` when a rule applies to every field or record in
the group:

- what counts as one record
- what rows to exclude
- whether to include all rows, only selected rows, or only active rows
- how to treat subtotals, summary rows, repeated headers, duplicates, and notes

Do not copy group rules into every field. That makes prompts longer and easier to
contradict.

## Wrapper prompts

Extract, reconcile, and QA wrappers should mainly carry the task frame:

- include the field specs from YAML
- include the source evidence available to the agent
- require JSON output in the expected shape
- ask reconcile to choose the best supported value
- ask QA to correct only values contradicted by source evidence

Do not hide field-specific rules inside wrapper prompts. Put durable rules in YAML.

## Good example

```yaml
effective_date:
  workflow_output_key: effective_date
  prompt:
    description: Date when the selected arrangement becomes effective.
    identifiers:
      - Effective Date
      - Start Date
      - Begins on
    instructions: Use the date tied to the selected or marked effective-date option. Do not use signature date, revision date, print date, or an unselected option's date. Return null if no selected effective date is shown.
    format: YYYY-MM-DD
    type: str
```

Why this works:

- It states the field meaning.
- It lists representative identifiers.
- It tells the agent which nearby dates are wrong.
- It explains how selected options confirm or reject the value.
- It gives the output format and null rule.

## Weak example

```yaml
effective_date:
  prompt:
    description: Effective date.
    identifiers:
      - Date
    instructions: Find the effective date.
    type: str
```

Why this fails:

- It does not explain what "effective" means.
- It treats every date label as equally useful.
- It gives no exclusion rule.
- It gives no output format.
- It cannot handle selected vs unselected options.

## Do not overfit

Do not add page numbers, one sample's option labels, exact answer-key values, or labels
that only exist to rescue a known benchmark miss. Add rules that would help on a new
document with the same field.

Use source evidence to improve the general rule. If the rule only works because you know
the answer for one sample, do not put it in the prompt.
