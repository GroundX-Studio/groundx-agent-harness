# 15. Repeating-group accuracy

How to author prompts for repeating-record groups (charges, meters, line
items, claims, schedules — any group that extracts to an array of records)
and how to iterate them with the field-level accuracy report. Domain-generic:
nothing here is invoice-specific.

Read this whenever a repeating group under-scores. Singleton/per-document
fields extract near-perfectly with a plain schema; repeating groups are where
accuracy work concentrates, and the failures fall into a small, fixed set of
causes. Diagnose the cause from the field-level report (`5_validation.md` §3),
then apply the matching prompt pattern below.

## 1. Read the field-level report first

Do not iterate on a group's record pass/fail rate — it conflates distinct
problems. Read `group_field_accuracy` (per field name within the group) and
`group_record_coverage` (matched / expected / extra / not_found). Each maps to
a different fix:

| Symptom in the report | Cause | Fix |
|---|---|---|
| One field `field-mismatch` across many records | non-verbatim values OR expected-answer artifact | §2 verbatim; confirm against the printed doc before treating as a miss |
| `not_found` records / a field `not-found` across records | missed rows / prompt too narrow | §3 capture-all |
| `extra` records | over-extraction (subtotals, recap boxes) | §4 exclusions |
| `extra` records that duplicate matched ones | cross-chunk duplicates | §5 dedup |
| A field `expected-null` everywhere | not a real target | nothing — excluded from the denominator |

A `field-mismatch` cluster is the one to investigate before touching the
prompt: compare the extracted value to the **printed document**, not just the
expected answers. Expected answers are often DB-normalized (normalized
addresses, multiplier-adjusted usage, sentinel codes) and diverge from what the
page shows. If the extraction matches the page, it is correct and the
expected-answer source is the artifact — record the divergence
(`6_known_limitations.md`), do not "fix" a correct extraction.

## 2. Verbatim values

Repeating records most often miss on description-like text fields: the model
paraphrases, truncates, or drops a trailing token (`Cost of gas*` → `Cost of
gas`, `Feb 2021 Weather Event` → `Feb`). Instruct the group to copy the
printed text exactly:

> Copy the line-item description **verbatim** as printed, including trailing
> symbols, dates, and qualifiers. Do not paraphrase, summarize, abbreviate, or
> drop tokens.

Apply the same verbatim rule to any field whose value is a printed label or
identifier rather than a normalized quantity.

## 3. Capture every row

One record per printed line item; do not merge, skip, or summarize. State the
boundary of the group explicitly so the model knows where rows start and stop:

> Extract one record for **every** line item in the charges table, top to
> bottom, including zero-dollar and credit lines. Do not stop early; do not
> combine related lines into one record.

If rows are missed (`not_found`), the prompt is usually too narrow or the
workflow step is reading only part of the document. Confirm the custom step
level and X-Ray readback map (`3_prompt_pipeline.md`) before tightening
wording.

## 4. Exclude subtotals, totals, and recap rows

Over-extraction (`extra` records) usually comes from the model pulling
subtotal, total, balance-forward, or recap-box lines as if they were line
items. Exclude them with explicit IS-NOT examples, in the group's own words:

> Extract only individual charge line items. Do **not** extract: subtotals,
> the total/amount-due line, previous-balance or balance-forward lines, or any
> summary/recap box that restates charges shown elsewhere.

IS-NOT examples are more reliable than abstract rules — name the exact row
types the document prints.

## 5. One row per record; dedup cross-chunk duplicates

When a workflow group aggregates across chunks, the same record can appear
twice (a charge that spans a page break, a meter summarized in two places).
Two defenses:

- Prompt: "Each physical row appears **once**; if the same line item is shown
  in multiple places, extract it a single time."
- Metadata: declare `unique_attrs` on the group so the runner dedups by a
  stable attribute set post-extraction. See `12_business_logic.md`.

Dedup is a record-coverage fix (drives `extra` down), not a field-accuracy
fix — verify it did not also drop a legitimately distinct record.

## 6. The iteration loop

1. Run the batch (`batch_extraction.py`) or re-score a captured X-Ray
   (`xray_to_extract` → `score_extraction.py`) — **no re-ingest** unless the YAML or
   prompt changed (`8_iteration_and_feedback.md` §6).
2. Read `group_field_accuracy` + `group_record_coverage`. Pick the **single
   worst field or coverage gap**, not the group's aggregate.
3. Classify its cause from §1. If the cause is an expected-answer artifact, record
   it and move on — do not change a correct extraction.
4. Apply the one matching prompt pattern (§2–§5) to that group's
   `prompt.instructions`, or add the metadata. Change one thing.
5. Re-compile, re-run, re-score. Confirm the targeted field improved and no
   other field regressed.
6. Stop when every remaining miss is a documented expected-answer artifact, a
   platform limitation, or an accepted convention (`5_validation.md` §7).

One field per iteration keeps cause and effect legible. A schema-wide rewrite
hides which change moved which number.
