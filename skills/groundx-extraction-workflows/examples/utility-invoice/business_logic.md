# Utility invoice hosted-logic intent

These are synthetic identity, relationship, conflict, and propagation rules a
customer might describe in conversation. They are recorded in `prompt.yaml` as
the supported metadata vocabulary. Cashbot compiles and dispatches the
metadata. GroundX Python owns generic identity deduplication, custom-output
reassembly, and relationship selection. Each hosted extraction service owns
only its service-specific policy and uses the shared SDK relationship selector.
Harness submits the YAML, captures raw hosted output, and compares it without
mutation.

## What the customer said, and how it maps

| In chat | Group | YAML intent |
|---|---|---|
| "There's only ever one statement per bill. Collapse repeats." | `statement` | `unique_attrs: [sp_inv_num]` |
| "A line item is the same charge if its printed description, start date, and amount match." | `charges` | `unique_attrs: [charge_description_as_printed, beg_chg_date, charge_amount]` |
| "Each charge is billed against a meter. Link them by meter number." | `charges` | `match_attrs: [meter_number]` |
| "Put the meter's service class on each related charge." | `charges` | `passthrough: {from: meters, fields: [service_class]}` |
| "If two sources disagree on a line's unit rate, keep the conflict visible." | `charges` | `conflict_attrs: [rate]` |
| "Meters are unique by meter number." | `meters` | `unique_attrs: [meter_number]` |

`unique_attrs` must describe genuine record identity. A shared description,
date, amount, or category is not enough when multiple legitimate rows can carry
the same values. Verify the hosted record count against the source after adding
or changing identity metadata.

## Expected hosted result

The supported product path should:

1. preserve one statement, meter, or charge for each declared identity;
2. relate charge rows to meters through `meter_number`;
3. propagate `service_class` only to related charge rows;
4. retain the account-level "Customer Service Charge" with null meter and
   service-class values; and
5. keep distinct rate values visible when the product contract supports
   `conflict_attrs`.

If raw `get_extract` does not reflect supported YAML intent, preserve the YAML,
workflow readback, raw output, and X-Ray, then file a product defect in the
owning repository. Do not add a Harness fallback.

## Legitimate nulls

`answer_key.json` includes nulls the comparator must treat as correct:

- `statement.budget_plan_name`: the synthetic account is on standard billing;
- `charges[2].rate` and `charges[2].meter_number`: the flat service charge has
  no unit rate and is not tied to a meter.

These exercise null-vs-miss classification in `references/5_validation.md`.
