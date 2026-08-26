# Hosted business logic ownership and YAML intent

Before any command here creates local output, read
[`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must
initialize and use its exact absolute run root. Ad-hoc work uses one dedicated
root. Settle or hand off useful results, delete raw evidence, verify absence,
and report what remains.

Start with the JSON the customer needs, then capture supported record identity
and relationship intent in source YAML. Cashbot only validates, compiles,
persists, and dispatches that metadata. GroundX Python owns generic identity
deduplication, custom-output reassembly, and relationship selection. Each
hosted extraction service owns only its service-specific policy and uses the
shared SDK relationship selector. Harness submits the YAML unchanged, captures
raw `get_extract`, preserves X-Ray, and compares artifacts. It never
deduplicates records, matches relationships, copies fields, surfaces synthesized
conflicts, or mutates extraction output.

If supported intent is absent from hosted output, stop and record a product
defect in the owning repository. Do not add a Harness matcher, postprocessor,
metadata sidecar, or fallback output path.

## Final shape and workflow grouping

Define the final customer JSON before choosing workflow groups. An
invoice-shaped extraction may have a document-level `statement`, repeating
`meters`, and repeating `charges` related by account number, meter number,
service address, or another printed identifier. Other domains should use names
that match their own output contract.

Custom workflow steps decide how fields execute. They do not define record
identity or relationships. Keep these concepts separate:

- final groups: JSON keys the customer reads;
- workflow groups: how extraction work is assigned;
- route map: where workflow fields write in the final JSON;
- identity and relationship intent: `unique_attrs`, `match_attrs`,
  `conflict_attrs`, and `passthrough` on final groups.

## YAML metadata vocabulary

All keys are optional and declared on final groups:

| Key | Shape | Customer intent |
|---|---|---|
| `unique_attrs` | `list[str]` | Fields that establish one record's identity for supported deduplication behavior. Include a genuine per-record key such as claim number, circuit ID, site ID, or meter number. Description, date, amount, and category alone can collapse distinct records that happen to share values. |
| `match_attrs` | `list[str]` | Printed fields that relate a child record to a parent record. |
| `conflict_attrs` | `list[str]` | Fields whose distinct values should be surfaced as `<field>__conflicts` rather than silently selected. |
| `passthrough` | `{"from": "<parent_group>", "fields": [...]}` | Parent fields the supported runtime should propagate to related child records. |

Example:

```yaml
meters:
  unique_attrs: [meter_number]
  conflict_attrs: [service_address]
  fields:
    meter_number: {...}
    service_address: {...}
charges:
  unique_attrs: [charge_description_as_printed, beg_chg_date, charge_amount]
  match_attrs: [meter_number]
  passthrough: {from: meters, fields: [service_address]}
  fields:
    meter_number: {...}
    charge_amount: {...}
```

Do not place these keys under workflow custom-step definitions. Do not encode
deduplication or relationship rules as field extraction instructions.

## Capture intent from conversation

Ask the customer:

| Question | YAML intent |
|---|---|
| When are two rows the same real record? | `unique_attrs` |
| Which printed values connect a child row to its parent? | `match_attrs` |
| Which disagreements must remain visible? | `conflict_attrs` |
| Which parent values should appear on each related child? | `passthrough` |

Confirm the expected record count after identity behavior. A successful extract
with far fewer records than the source is evidence that identity is too broad,
not proof that deduplication worked.

## Product gaps

When the customer needs a computed total, conditional derivation, multi-hop
join, unit conversion, sequencing rule, or another behavior outside the
supported vocabulary, record:

1. the required customer result;
2. the YAML intent and hosted output observed;
3. why the current product contract cannot express it;
4. the owning repository and smallest general product change.

Harness remains an authoring, capture, and comparison surface. Missing hosted
behavior is never a reason to add local output construction.
