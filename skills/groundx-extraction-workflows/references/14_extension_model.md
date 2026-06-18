# 14. Extension model

How this system grows. Most changes are YAML edits; exactly one kind of change
needs runner code. Knowing which axis a request lands on tells you what to touch
and what to prove.

## The three axes (plus the one that needs code)

| Change | Example | What edits | Code? | Proof |
|---|---|---|---|---|
| **New field / concept** | add `delivery_point_id`; tighten a null rule | one field def in `prompt.yaml` | none | re-compile; re-compare the touched field |
| **New use case in a domain** | utility bill → telecom invoice; add dedup/link rules | `prompt.yaml` fields + per-group business-logic metadata | none | re-compile; the metadata changes the post-extraction output |
| **New domain** | invoice → insurance claim | new `examples/<domain>/` custom-step YAML + answer-key fixture + smoke eval | none unless a new primitive is needed | fixture compiles, validates routes, and scores its answer key |
| **New primitive** | graph / sequencing linking the metadata can't express | a runner primitive in `templates/business_logic.py` | **yes — escalation signal** | a unit test for the primitive |

The first three are declarative. Only the fourth — a genuinely new
**aggregation or linking capability** — touches runner code, and it is the
escalation signal feeding the platform/SDK migration track, not a per-customer
fork.

### Axis 1 — new field

Add a field def under a group's `fields:`. Give it `description`, `identifiers`,
`instructions`, and `type` (see `2_schema_design.md`). A field whose value is
legitimately absent on some documents states that in `instructions` ("leave empty
when …") and the answer key records it as `null`; the comparator treats a correct
null as a PASS (`5_validation.md`).

### Axis 2 — new use case in a domain

The platform extracts records; it does not dedup, link across groups, surface
conflicts, or copy parent fields onto children. Those are expressed as per-group
metadata in `prompt.yaml` and run client-side by `templates/business_logic.py`:

| Metadata key | Primitive | Effect |
|---|---|---|
| `unique_attrs: [...]` | dedup | collapse records sharing normalized values of these fields |
| `match_attrs: [...]` | fk-link | link this group's records to a parent group on these fields |
| `passthrough: {from, fields}` | passthrough | copy parent fields onto each linked child |
| `conflict_attrs: [...]` | conflict-surface | surface disagreeing values as `<field>__conflicts: [...]` |

These keys are **consumed client-side and never reach the workflow JSON** — the
compiler keeps only `fields` in the `extract` block. So adding them is a YAML-only
change. See `examples/utility-invoice/business_logic.md` for a worked "from chat"
capture, and `12_business_logic.md` for the primitive semantics.

### Axis 3 — new domain

A new document family gets its own `examples/<domain>/` directory and custom-step
YAML. Define `workflow.custom_steps`, assign each group with
`workflow_step: <name>`, and set `workflow_output_key` on routed fields. The
compiler emits `customSteps`, `outputRoutes`, and `leafFields`, and local readback
can map `customChunkOutputs`, `customSectionOutputs`, and
`customDocumentOutputs` back to final JSON paths.

Group names are free. A new domain needs **no runner code** unless it also needs
a new primitive (axis 4).

### Axis 4 — new primitive (the only code path)

A domain needs runner code only when it requires a linking or aggregation
capability the metadata vocabulary cannot express (computed totals, conditional
rollups, multi-hop joins, unit conversions). Do **not** fork
`business_logic.py` per customer. Log the gap and escalate; see
`12_business_logic.md` ("the primitive gap") and `6_known_limitations.md`. This is
the signal that feeds the platform/SDK migration track.

## Fixture layout convention

In-repo fixtures are synthetic or anonymized and CI-safe — **never real customer
data**. Real customer documents and answer keys stay in ignored or out-of-repo
paths; see `customer-onboarding.md`.

```
examples/<domain>/
  prompt.yaml            # custom-step workflow metadata + business metadata
  data/answer_key.json   # runner output shape; include a legitimate null when the domain has one
  business_logic.md      # the "from chat" rules mapped to the metadata vocabulary
  README.md              # the end-to-end loop for this fixture
```

A new-domain fixture should include `prompt.yaml`, `README.md`, and
`data/answer_key.json`. Compile-only proof is too shallow for promoted examples:
it catches hardcoded group names, but not route/readback or scorer shape drift.

## Fitness gates that keep the compiler honest

Three gates prevent silent re-hardcoding of the invoice group names and
non-invoice scorer drift:

1. **Non-invoice compile + route shape** — a fixture whose group names are not
   invoice names (`examples/insurance-claim/`) must compile to valid workflow
   JSON, and its answer key must contain every compiled final route.
2. **Non-invoice score smoke** — the same fixture's answer key must be valid
   runner output shape for singleton and repeating groups.
3. **Field-coverage gate** — a YAML's fields must cover the target catalog's
   fields (YAML fields ⊇ catalog fields).

Run `python templates/compile_workflow.py <prompt.yaml>` to compile a fixture
offline (exit 0 = pass; missing custom workflow metadata is a hard error). The
skill eval suite asserts the smoke compile, custom-step compile, field coverage,
null-vs-miss classification, and at least one business-logic primitive changing
the output.
