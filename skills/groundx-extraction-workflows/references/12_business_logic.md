# 12. Post-extraction business logic

GroundX extracts records. It does not dedup them, link them across groups,
surface their conflicts, or copy parent fields onto children. Customers
routinely need that. This skill supplies it as a small set of declarative,
client-side primitives driven by final-group YAML metadata, applied **after**
extraction by `templates/business_logic.py`.

Runs client-side, not on the platform. For current custom workflows, the runner
aggregates X-Ray output into the final customer-facing group shape such as
`{"statement": {...}, "charges": [...], "meters": [...]}` (see
`templates/xray_to_extract.py`), then `run_extraction.py` calls
`apply_business_logic(extract_dict, metadata)` before writing
`final_output.json`. `output.json` remains the raw GroundX `get_extract`
payload when available. Run this logic on the final data shape unless a
workflow-scoped primitive is
explicitly documented. None of this metadata reaches the GroundX workflow:
`compile_workflow.py` reads it from `PreparedExtractionYaml.final_group_metadata`
and strips it from workflow groups, so the keys never become extract fields.
`run_extraction.py` persists that final-group metadata as
`business_logic_metadata.json` in the run directory so `--resume` can apply the
same local final-output logic without recompiling or re-reading source YAML.

## Final shape vs. workflow grouping

Start with the JSON the customer wants, not the workflow execution plan. In an
invoice-shaped extraction, a document-level `statement`, a list of `meters`,
and a list of `charges` may be related by values such as account number, meter
number, service address, or a charge label. Those relationships belong to the
final groups and to the custom logic that consumes their metadata.

Custom workflow steps do not create those relationships. They only decide how
each real group executes on GroundX. Do not infer charge-to-meter matching,
dedupe rules, passthrough, reconcile behavior, or QA scope from custom step
names.

For projects with a custom manager, pass the final-group metadata into the
manager's reconcile, QA, and post-extraction steps explicitly. Keep these
concepts separate:

- final groups: the JSON keys the customer reads
- workflow groups: how extraction work is assigned
- route map: where each workflow field writes in the final JSON
- relationship metadata: keys such as `unique_attrs`, `match_attrs`,
  `conflict_attrs`, and `passthrough`

## 1. Metadata vocabulary

Declared per final group in the extraction YAML, all optional:

| Key | Shape | Meaning |
|---|---|---|
| `unique_attrs` | `list[str]` | Records sharing normalized values of these fields are duplicates: keep the first, merge non-null fields from the dropped duplicates onto it. |
| `match_attrs` | `list[str]` | Cross-group foreign key linking this (child) group's records to a parent group's record sharing the same normalized values. |
| `conflict_attrs` | `list[str]` | When records that should agree disagree on these fields, surface every distinct value as `<field>__conflicts: [values]` instead of silently picking one. |
| `passthrough` | `{"from": "<parent_group>", "fields": [...]}` | Copy those fields from the linked parent record onto each child record. Uses this group's `match_attrs` as the join key. |

Example:

```yaml
meters:
  unique_attrs: [meter_number]
  conflict_attrs: [service_address]
  fields:
    meter_number: {...}
    service_address: {...}
charges:
  unique_attrs: [meter_number, charge_amount]
  match_attrs: [meter_number]
  passthrough: {from: meters, fields: [service_address]}
  fields:
    meter_number: {...}
    charge_amount: {...}
```

Do not declare these keys under workflow custom step definitions. Final business
metadata remains attached to final groups.

## 2. Primitives

`templates/business_logic.py` (stdlib-only, pure functions):

- `dedup(records, unique_attrs)` — collapse duplicates by normalized key,
  keeping the first and merging non-null fields from dropped duplicates.
- `link(child, parent, match_attrs)` — annotate each child with its matched
  parent record under `_parent` (None when no parent matches).
- `surface_conflicts(records, conflict_attrs)` — add `<field>__conflicts`
  when records carry more than one distinct non-null value for a field.
- `apply_passthrough(child, parent, match_attrs, fields)` — copy parent
  `fields` onto matched children (does not overwrite a non-null child value).
- `apply_business_logic(doc, group_metadata)` — orchestrator. Per group:
  surface intra-group conflicts (among the records dedup is about to collapse,
  so the disagreement is not lost) → dedup → passthrough from the deduped
  sibling groups. A **no-op when `group_metadata` is empty/absent**, so a YAML
  with none of these keys produces unchanged output.

Normalization (strip + case-insensitive + date) matches `templates/score_extraction.py`,
so a record judged a duplicate or a foreign-key match here is one the
comparator treats as equal.

## 3. The primitive gap — escalate, do not fork

These primitives are intentionally small. When a customer needs logic they
cannot express — computed totals or rollups, conditional derivation,
multi-hop joins, unit conversion, validation rules — **do not fork
`business_logic.py` per customer.** Log the gap (what the customer needs, why
the existing primitives cannot express it, the smallest new primitive that
would) and escalate, following the limitation-handling pattern in
`6_known_limitations.md`. A new primitive should be general enough to earn its
place in the shared vocabulary above, not a one-customer special case.
