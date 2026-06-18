# 13. Customer resource intake & chat-driven authoring

Use this reference at the **front of a customer extraction pilot**: a customer
shares resources, you turn them into a field inventory, you draft `prompt.yaml`,
you chat to capture business logic, and you check field coverage before the
first run. `customer-onboarding.md` lists *what to confirm*; this file is the
*how* — resources → inventory → draft YAML → chat → coverage check. After the
coverage check passes, hand off to the extraction loop in `1_extraction_loop.md`.

This is methodology, not a platform-operation guide. Keep YAML the durable
artifact; route workflow registration, ingest, polling, and extract retrieval to
`groundx-api` (see `customer-onboarding.md` §API handoff).

## 1. Ask for the right resources

Request these before drafting anything. Note which are missing rather than
inventing substitutes.

| Resource | Why it matters | If missing |
|---|---|---|
| **Field catalog** (spreadsheet, schema, data dictionary, or PDF listing expected fields) | The authoritative set of output fields; drives the coverage gate in §5 | Reconstruct from sample docs + the owner's answers; flag that coverage cannot be verified |
| **Sample documents** | Ground the field inventory in what actually appears on the page | Cannot ground identifiers/instructions; ask for at least one representative file |
| **Answer keys** (ground-truth JSON in runner output shape) | Enables `score_extraction.py` scoring and the per-field accuracy bar | Defer accuracy claims; do shape-only proof |
| **Naming constraints** | Required output key names, casing, downstream column names | Keep the customer-facing YAML/JSON key when possible; choose a safe `workflow_output_key` for custom outputs |
| **Null semantics** | Which fields are legitimately blank vs. always present; how "not applicable" is encoded | Treat all fields as possibly-null; confirm before scoring |

Also confirm, per `customer-onboarding.md`: document type and business outcome,
the field owner, whether files arrive in batches or over time (manual
batch-readiness trigger), and storage permission for samples and answer keys.

## 2. Field catalog → field inventory

Turn the catalog into a flat inventory the agent reasons over. For each field
record:

- **field name** — the customer's name; this becomes the YAML key and JSON output key
  inside the final group when it is valid for the desired output contract
- **scope** — `singleton` (appears once per document) or `repeating` (one value per
  record in a list). Scope decides the custom step kind: singletons use
  `kind: instruct`; repeating records use `kind: keys` or `kind: summary`
- **null rule** — always present, sometimes null, or never null. Records the
  null-vs-miss expectation `score_extraction.py` uses (legitimate null = PASS, not a miss)
- **required output name** — the exact key the downstream system expects, if it
  differs from the catalog label. This is separate from `workflow_output_key`,
  which is an internal custom-output key and must match
  `^[a-z][a-z0-9_]{0,63}$`. If the customer-facing key is not safe for custom
  outputs, keep it as the YAML field key and choose a safe `workflow_output_key`.

Cross-check the catalog against the sample documents: every catalog field should
be locatable on a sample, and any field on the sample that the catalog omits is a
question for the owner, not a silent addition. A field whose scope is ambiguous
from the catalog (e.g. "could be one or many") is resolved by looking at the
samples — see `3_prompt_pipeline.md` §6.3 decision rules.

## 3. Inventory → draft `prompt.yaml`

### 3.1 Choose workflow steps

Group the inventory by scope, then choose how each workflow group executes.
Harness-authored YAML sets top-level `extraction_policy_version: v1`, defines
top-level `workflow.custom_steps`, assigns groups with `workflow_step: <name>`,
puts `workflow_output_key` on each directly routed field, and declares
`workflow.agent_chain` with one branch per executable workflow group. Keep each
executable custom step to 30 fields or fewer.

Do not force an unrelated document into invoice-shaped group names. A claim form,
contract, or schedule should use group names that match the desired JSON output
and custom steps that match the extraction shape; see `2_schema_design.md` §1.

### 3.2 Write field prompts

For each inventory field, write the field anatomy from `2_schema_design.md` §2:
`description`, `identifiers` (1–3 labels seen on the samples), `instructions`
(one concrete rule per line, grounded in the samples), `type`, and `format` for
dates/codes. For repeating groups, add the group-level `prompt.instructions`
that distinguishes a real record from a subtotal/header (`2_schema_design.md`
§3). Keep each group ≤ 30 fields (`2_schema_design.md` §1.5).

## 4. The chat step — capturing business logic

Field prompts extract values; **business logic** is everything that happens to
those values after extraction (dedup, linking, conflict surfacing, propagation).
The customer holds this knowledge — elicit it in conversation and record it as
**per-group YAML metadata** the runner executes client-side post-extraction. Do
not ask the customer to build this logic themselves.

Ask, per repeating group and per cross-group relationship:

| Question to the customer | Metadata to record | Group key |
|---|---|---|
| "When are two of these records actually the same record?" | dedup: collapse records sharing the identifying attrs | `unique_attrs: [..]` |
| "Does a record in group A point at a record in group B? On what?" | cross-group link (foreign key) between groups | `match_attrs: [..]` |
| "If the same field shows two different values, do you want both flagged?" | surface disagreeing values instead of silently picking one | `conflict_attrs: [..]` |
| "Should a parent field be copied onto each child record?" | propagate parent fields across a relationship | `passthrough: {from: <parent_group>, fields: [..]}` |

These are declarative lists of attribute (field) names attached to the group in
the YAML, alongside `fields:` and `prompt:`:

```yaml
extraction_policy_version: v1

workflow:
  custom_steps:
    - name: charge_lines
      level: chunk
      kind: keys
  agent_chain:
    - parallel:
        - group: charges
          chain: [reconcile_charges, save_charges]

charges:
  workflow_step: charge_lines
  unique_attrs: [charge_description_as_printed, charge_amount]   # dedup identical rows
  match_attrs: [meter_number]                                    # link to the meters group
  conflict_attrs: [charge_amount]                                # flag disagreeing amounts
  passthrough: {from: statement, fields: [account_number]}        # copy from the statement group
  fields:
    charge_description_as_printed:
      workflow_output_key: charge_description_as_printed
      prompt: { ... }
    charge_amount:
      workflow_output_key: charge_amount
      prompt: { ... }
```

Every attr name must be a field that exists in the inventory/YAML. Record only
the logic the customer actually states; a YAML that declares none runs
extract-only. If the customer describes behavior these four primitives cannot
express (graph/sequencing links, multi-hop resolution), do not invent a workaround
— surface it as a primitive gap per the escalation signal in the design and
`6_known_limitations.md` §3.

## 5. Field-coverage check before running

Before the first run, verify the authored YAML covers the customer's catalog:
**every catalog field name must appear as a field in the YAML** (YAML fields ⊇
catalog fields). A missing field means the extraction will silently omit
something the customer asked for.

Run `templates/check_field_coverage.py` (catalog as JSON list or CSV of field
names) to list any catalog fields absent from the YAML:

```
python templates/check_field_coverage.py prompt.yaml catalog.json
```

Exit code is non-zero when fields are missing. Extra YAML fields beyond the
catalog are allowed (the gate is one-directional). Resolve every missing field —
add it to the right group or confirm with the owner that it is intentionally out
of scope — before handing off to `1_extraction_loop.md`. A field renamed for
downstream output is handled by the comparison alias map, not by dropping the
field (`6_known_limitations.md` §1).

## Do not

- Draft a schema from a vague "extract everything" brief; start from the catalog
  and samples.
- Add fields seen on a sample but absent from the catalog without asking the owner.
- Bake business logic into field `instructions`; record it as group metadata.
- Skip the coverage check; a silently uncovered catalog field is the common pilot miss.
- Commit customer catalogs, samples, or answer keys to tracked paths without
  explicit permission (`customer-onboarding.md` §Do not).
