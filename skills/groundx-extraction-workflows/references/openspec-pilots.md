# OpenSpec Pilots

OpenSpec is optional for quick extraction tasks. Use it for serious pilots when the
work needs durable requirements, acceptance criteria, sample inventory, schema decisions,
comparison reports, or iteration notes that multiple agents or people will revisit.

## When To Use

Use an OpenSpec pilot when:

- the customer provides multiple sample documents or expected answers,
- target fields need field-owner confirmation,
- table or repeating-record structure matters,
- accuracy will be measured against a comparison report,
- the pilot needs a handoff between agents, engineers, or customer stakeholders.

For quick one-document schema drafting, stay in the normal extraction loop.

## Folder Boundary

Tracked OpenSpec artifacts may describe requirements, design decisions, and task status.
Do not put customer documents, expected answers, comparison outputs, private pilot notes,
credentials, or scratch run outputs under tracked `openspec/specs/` or
`openspec/changes/` unless the customer has explicitly approved sharing them.

Keep private work in ignored `openspec/work/`, ignored `openspec/private/`, or outside
the repository.

## Suggested OpenSpec Shape

- `proposal.md`: document type, business outcome, field owner, sample readiness, output
  handoff, non-goals.
- `specs/<pilot>/spec.md`: target fields, repeating records, table requirements,
  accepted formats, and comparison scenarios.
- `design.md`: YAML group strategy, workflow registration strategy, on-prem or API
  constraints, expected X-Ray/debug loop.
- `tasks.md`: sample intake, expected-answer review, YAML draft, compile, register, ingest,
  compare, field iteration, acceptance, and handoff.

## Acceptance Criteria

Pilot specs should cover:

- per-field expected value and accepted normalization,
- repeating-record row identity and dedupe rules,
- table row and column preservation when table structure matters,
- totals, subtotals, merged cells, and currency/date formats when relevant,
- allowed WARN conditions,
- maximum iteration budget,
- what artifact is delivered at the end.

Do not promise benchmark accuracy from one or two examples. Validate obvious
expected-answer mismatches before tightening prompts.
