# Utility invoice — business-logic rules (captured from chat)

These are the linking / dedup / conflict rules a customer would describe in
conversation, expressed in the declarative metadata vocabulary that
`templates/business_logic.py` runs **client-side, after** the GroundX platform
returns the aggregated extract. The platform extracts records; it does not
dedup, link, surface conflicts, or copy parent fields onto children — so these
rules live in `prompt.yaml` as per-group metadata, not as workflow fields. The
compiler drops them from the workflow JSON.

This is the "new use case in a domain = YAML + metadata, no runner code" axis of
the extension model (`references/14_extension_model.md`).

## What the customer said, and how it maps

| In chat | Group | Metadata | Primitive |
|---|---|---|---|
| "There's only ever one statement per bill — collapse repeats." | `statement` | `unique_attrs: [sp_inv_num]` | dedup |
| "A line item is the same charge if the description, start date, and amount all match — drop the duplicate." | `charges` | `unique_attrs: [charge_description_as_printed, beg_chg_date, charge_amount]` | dedup |
| "Each charge is billed against a meter; link them by meter number." | `charges` | `match_attrs: [meter_number]` | fk-link |
| "Put the meter's service class on the charge so we can group spend by commodity." | `charges` | `passthrough: { from: meters, fields: [service_class] }` | passthrough |
| "If two chunks disagree on a line's unit rate, show both — don't pick one silently." | `charges` | `conflict_attrs: [rate]` | conflict-surface |
| "Meters are unique by meter number." | `meters` | `unique_attrs: [meter_number]` | dedup |

## Order of operations

`apply_business_logic` runs, per group: **dedup → passthrough → conflict-surface**.
Dedup runs first across all groups so that linking and passthrough read collapsed
sibling groups. For this fixture:

1. `meters` and `statement` and `charges` are each deduped on their `unique_attrs`.
2. `charges` are linked to `meters` on `meter_number`; `service_class` is copied
   onto each matched charge.
3. The "Customer Service Charge" line carries `meter_number: null` and so does not
   link — it keeps a null `service_class`. That is a legitimate null, not a miss.
4. `rate` conflicts (if any chunk disagreed) surface as `rate__conflicts: [...]`.

## Legitimate nulls in this fixture

`answer_key.json` deliberately includes nulls the comparator must treat as
**correct null**, not **failed extraction**:

- `statement.budget_plan_name` — the synthetic account is on standard billing, so
  there is no plan to read. The field prompt instructs the extractor to leave it
  empty rather than invent one.
- `charges[2].rate` and `charges[2].meter_number` — the flat "Customer Service
  Charge" has no unit rate and is not tied to a meter.

These exercise null-vs-miss classification (`references/5_validation.md`): a `null`
in expected-answer JSON that the extraction also returns null is a PASS, distinct
from a field that should have a value but came back empty.
