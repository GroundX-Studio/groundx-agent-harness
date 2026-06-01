# 14. Extension model

How this system grows. Most changes are YAML edits; exactly one kind of change
needs runner code. Knowing which axis a request lands on tells you what to touch
and what to prove.

## The three axes (plus the one that needs code)

| Change | Example | What edits | Code? | Proof |
|---|---|---|---|---|
| **New field / concept** | add `delivery_point_id`; tighten a null rule | one field def in `prompt.yaml` | none | re-compile; re-compare the touched field |
| **New use case in a domain** | utility bill → telecom invoice; add dedup/link rules | `prompt.yaml` fields + per-group business-logic metadata | none | re-compile; the metadata changes the post-extraction output |
| **New domain** | invoice → insurance claim | new `examples/<domain>/` + a domain profile **or** explicit per-group `slot:`, + a smoke eval | none unless a new primitive is needed | the smoke fixture compiles |
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

A new document family gets its own `examples/<domain>/` directory and resolves
each group's slot one of two ways:

- **Domain profile** — add `templates/domains/<domain>.yaml` mapping group names
  to slots, then declare `domain: <domain>` in the YAML (like `invoice`).
- **Explicit slots** — declare `slot:` on each group, no profile needed (like the
  `insurance-claim` smoke fixture).

Either way the group names are free; only the **slot** is constrained, to the
three proven slots (`chunk-instruct`, `chunk-keys`, `chunk-summary` — see
`2_schema_design.md`). A new domain needs **no runner code** unless it also needs
a new primitive (axis 4).

### Axis 4 — new primitive (the only code path)

A domain needs runner code only when it requires (1) more groups than proven
slots, (2) a slot carrying multiple groups, (3) an aggregation kind the slot grid
lacks, or (4) linking/sequencing the metadata vocabulary cannot express (computed
totals, conditional rollups, multi-hop joins, unit conversions). Do **not** fork
`business_logic.py` per customer. Log the gap and escalate — see
`12_business_logic.md` ("the primitive gap") and `6_known_limitations.md`. This is
the signal that feeds the platform/SDK migration track.

## Fixture layout convention

In-repo fixtures are synthetic or anonymized and CI-safe — **never real customer
data**. Real customer documents and answer keys stay in ignored or out-of-repo
paths; see `customer-onboarding.md`.

```
examples/<domain>/
  prompt.yaml            # domain: <domain> + metadata, OR explicit slot: per group
  data/answer_key.json   # runner output shape, with at least one legitimate null
  business_logic.md      # the "from chat" rules mapped to the metadata vocabulary
  README.md              # the end-to-end loop for this fixture
```

A **compile-smoke** fixture (proving a non-invoice domain compiles) can be
minimal — just `prompt.yaml` + `README.md`, no answer key (see
`examples/insurance-claim/`).

## Fitness gates that keep the compiler honest

Two gates prevent silent re-hardcoding of the invoice group names:

1. **Non-invoice smoke compile** — a fixture whose group names are not invoice
   names (`examples/insurance-claim/`) must compile to valid workflow JSON.
2. **Field-coverage gate** — a YAML's fields must cover the target catalog's
   fields (YAML fields ⊇ catalog fields).

Run `python templates/compile_workflow.py <prompt.yaml>` to compile a fixture
offline (exit 0 = pass; a bad slot or missing slot is a hard error). The skill
eval suite asserts the smoke compile, generic-slot compile, field coverage,
null-vs-miss classification, and at least one business-logic primitive changing
the output.
