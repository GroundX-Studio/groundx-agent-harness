# 14. Extension model

How this system grows. Most changes are YAML edits. Missing identity,
relationship, or aggregation behavior requires a product change in its owning
repository, never Harness runner code.

## The three axes (plus the one that needs code)

| Change | Example | What edits | Code? | Proof |
|---|---|---|---|---|
| **New field / concept** | add `delivery_point_id`; tighten a null rule | one field def in `prompt.yaml` | none | server-validate; re-compare the touched field |
| **New use case in a domain** | utility bill to telecom invoice; add dedup/link intent | `prompt.yaml` fields + per-group identity/relationship metadata | none in Harness | server-validate; verify hosted output and compare raw artifacts |
| **New domain** | invoice to insurance claim | new `examples/<domain>/` custom-step YAML + expected-answer fixture + smoke eval | none in Harness | server validation passes, routes are correct, and expected-answer JSON scores |
| **New product behavior** | graph or sequencing relationship the metadata cannot express | Cashbot for compilation/dispatch, GroundX Python for generic identity/reassembly/selection, or the owning hosted extraction service for its service policy | **product change, not Harness code** | owner tests plus hosted output verification |

The first three are declarative Harness authoring changes. The fourth is a
product escalation, not a local fallback.

### Axis 1 — new field

Add a field def under a group's `fields:`. Give it `description`, `identifiers`,
`instructions`, and `type` (see `2_schema_design.md`). A field whose value is
legitimately absent on some documents states that in `instructions` ("leave empty
when …") and the expected-answer JSON records it as `null`; the comparator
treats a correct null as a PASS (`5_validation.md`).

### Axis 2 — new use case in a domain

Capture supported identity and relationship intent as per-group metadata in
`prompt.yaml`:

| Metadata key | Primitive | Effect |
|---|---|---|
| `unique_attrs: [...]` | dedup | collapse records sharing normalized values of these fields |
| `match_attrs: [...]` | fk-link | link this group's records to a parent group on these fields |
| `passthrough: {from, fields}` | passthrough | copy parent fields onto each linked child |
| `conflict_attrs: [...]` | conflict-surface | surface disagreeing values as `<field>__conflicts: [...]` |

These keys originate in source YAML. Cashbot only validates, compiles,
persists, and dispatches them. GroundX Python owns generic identity
deduplication, custom-output reassembly, and relationship selection. Each
hosted extraction service owns only its service-specific policy and uses the
shared SDK relationship selector. Harness submits the YAML and compares raw
hosted output without executing the rules. See
`examples/utility-invoice/business_logic.md` for a worked "from chat"
capture, and `12_business_logic.md` for the primitive semantics.

### Axis 3 — new domain

A new document family gets its own `examples/<domain>/` directory and custom-step
YAML. Define `workflow.custom_steps`, assign each group with
`workflow_step: <name>`, declare its processing `role:`, and set
`workflow_output_key` on routed fields. The
server compiler emits `customSteps`, `outputRoutes`, and `leafFields`, and readback
can map `customChunkOutputs`, `customSectionOutputs`, and
`customDocumentOutputs` back to final JSON paths.

Group names are free and never imply processing roles. A new domain needs no
Harness runner code.

### Axis 4 — new product behavior

A linking or aggregation capability outside the metadata vocabulary, such as a
computed total, conditional rollup, multi-hop join, or unit conversion, belongs
in the owning product repository. Record the missing hosted contract and
escalate through `12_business_logic.md` and `6_known_limitations.md`. Do not add
a Harness implementation.

## Fixture layout convention

In-repo fixtures are synthetic or anonymized and CI-safe — **never real customer
data**. Real customer documents and expected answers stay in ignored or
out-of-repo paths; see `customer-onboarding.md`.

```
examples/<domain>/
  prompt.yaml            # custom-step metadata + identity/relationship intent
  data/answer_key.json   # synthetic expected-answer JSON in runner output shape
  business_logic.md      # customer intent mapped to hosted metadata
  README.md              # the end-to-end loop for this fixture
```

A new-domain fixture should include `prompt.yaml`, `README.md`, and
`data/answer_key.json`. Offline topology proof is too shallow for promoted examples:
it catches hardcoded group names, but not route/readback or scorer shape drift.

## Fitness gates that keep the authoring path honest

Three gates prevent silent re-hardcoding of the invoice group names and
non-invoice scorer drift:

1. **Non-invoice server validation + route shape**: a fixture whose group names
   are not invoice names (`examples/insurance-claim/`) must pass server
   validation, and its expected-answer JSON must contain every final route.
2. **Non-invoice score smoke** — the same fixture's expected-answer JSON must be valid
   runner output shape for singleton and repeating groups.
3. **Field-coverage gate** — a YAML's fields must cover the target catalog's
   fields (YAML fields ⊇ catalog fields).

Validate a fixture with the server (`gx.workflows.validate(name=..., yaml=...)`).
Offline topology checks do not prove server acceptance. The skill eval suite
asserts topology shape, custom-step coverage, field coverage,
null-vs-miss classification, and hosted ownership guidance for identity and
relationship intent.
