# 5. Validation

How the comparison harness scores extraction output against expected answers,
how to map reviewer-provided expected answers before scoring, and how to read
its report.

## 1. The compare loop

The comparator (`skills/groundx-extraction-workflows/templates/score_extraction.py`) reads the
extracted JSON and a runner-shaped JSON expected-answer file and emits a
field-by-field report:

```
============================================================
EXTRACTION COMPARISON
============================================================

Answer key: 23 statement fields, 3 charges
Extraction: 23 statement fields, 3 charges

------------------------------------------------------------
STATEMENT FIELDS
------------------------------------------------------------
  ✅ acct_level_1: PASS
  ✅ inv_date: PASS
  ⚠️  billed_company_city: WARN (casing)
       Expected:  DANVILLE
       Extracted: Danville
  ✅ tot_amt_due: PASS
  ❌ pmts_app_thru_date: FAIL
       Expected:  2026-01-22
       Extracted: 2026-01-10

Statement: 22/23 passed

------------------------------------------------------------
CHARGES
------------------------------------------------------------
  [PASS] Classic Cable - Bulk: PASS
  [PASS] Franchise Fee: PASS
  [FAIL] FCC Regulatory Fee: FAIL
       line_item_amount: expected '0.40' got '0.04' [field-mismatch]

  per-field accuracy (charges):
    line_item_amount: 2/3 (67%)  [0 not-found, 1 mismatch]
    line_item_description: 3/3 (100%)

charges: 5/6 fields, 3/3 records matched, 0 extra

============================================================
SUMMARY
============================================================
  singleton fields: 22/23
  charges: 5/6 fields (83%), 3/3 records
```

PASS is the goal. WARN means a known-acceptable discrepancy. FAIL means
the field needs a tighter prompt or escalation. For groups, a single bad
field no longer zeroes the record — the per-field breakdown names exactly
what to fix.

### 1.1 Three ways to score

| tool | scope | ingest? |
|---|---|---|
| `score_extraction.py output.json expected_answers.json` | one document, raw GroundX `get_extract` output | no (offline) |
| `score_extraction.py final_output.json expected_answers.json` | one document, intentional local final output scoring | no (offline) |
| `batch_extraction.py …` | a folder of documents | **yes** — live ingest + extract + score + aggregate |
| `batch_score.py <run_dir> --keys-dir expected_answers/` | a captured run (a `batch_extraction` `--out`) | **no** — re-scores raw `<doc>.extracted.json` offline |
| `batch_score.py <run_dir> --keys-dir expected_answers/ --artifact-kind final` | a captured run's local final output | **no** — re-scores `<doc>.final_output.json` offline |

`batch_score.py` is the economical iteration loop: ingest **once** with
`batch_extraction`, then re-score the captured set as many times as you like —
after fixing an expected-answer mapping, comparison logic, or to score the same
run on another machine — **without paying for ingest again**. It imports only
the SDK-free `score_extraction` engine, so it runs anywhere with no GroundX
credentials. `aggregate_reports` lives in `score_extraction` and is shared by
both `batch_extraction` (live) and `batch_score.py` (offline).

Artifact names matter:

- `output.json` and `<doc>.extracted.json` are raw GroundX `get_extract`
  responses.
- `xray_diagnostic.json` and `<doc>.xray_diagnostic.json` are local X-Ray
  reconstructions for debugging. Do not score them as clean raw extraction.
- `final_output.json` and `<doc>.final_output.json` are local final outputs
  after diagnostic reconstruction and optional business logic. Score them only
  when that is the explicit goal.

### 1.2 Expected-answer formats and mapping

Expected answers may arrive as runner-shaped JSON, spreadsheets, documents,
text files, PDFs, or human-review notes. Only runner-shaped JSON goes directly
into `score_extraction.py`; every other format must be converted or mapped
first.

When expected answers and extraction output disagree:

1. Ignore fields where both sides agree.
2. Inspect the source document for each conflict.
3. Decide whether the expected answer, extraction value, or neither value is
   source-supported.
4. Score only fields that can be mapped and adjudicated.
5. Mark unsupported reviewer notes, schema mismatches, or ambiguous source
   evidence as unscored or WARN with rationale.
6. Count improvements and regressions against the same adjudicated field set.
7. Do not claim final improvement unless a new live raw `output.json` exists,
   or the report is explicitly labeled as diagnostic/local-final.

Keep a minimal mapping record for each reviewed field:

| field | meaning |
|---|---|
| `field_path` | JSON path in the runner output, such as `/claim/loss_date` |
| `expected_source_location` | where the expected answer came from: sheet tab + cell, document page/section, PDF page, text line, or reviewer note |
| `normalized_expected_value` | value after format normalization |
| `extracted_value` | value from `output.json` or the explicitly chosen local-final artifact |
| `source_support` | `expected_supported`, `extraction_supported`, `neither_supported`, or `ambiguous` |
| `scoreability` | `score`, `warn`, or `unscored` |
| `rationale` | one sentence explaining the decision |

## 2. Comparison rules

The comparator normalizes both expected and extracted values before
comparing, to avoid false negatives from trivial formatting differences.

### 2.1 Date normalization

Date strings in the form `M/D/YYYY` (or `MM/DD/YYYY`) are normalized to
`YYYY-MM-DD` before comparison. This means a CSV cell `1/22/2026` matches
an extracted value `2026-01-22` without false negative.

The normalization rule applies only when the value contains a `/` and is
≤10 characters long. Longer strings or strings without slashes are passed
through unchanged.

### 2.2 Float tolerance

Numeric fields are compared with a `0.01` tolerance. Both expected and
extracted values are parsed as floats; if their absolute difference is
under `0.01`, the field passes. This avoids false negatives from
representations like `38.99` vs `38.990` or `36.75` vs `36.7500`.

If float parsing fails for either value, the comparator falls back to
string comparison.

### 2.3 String comparison

String fields are compared case-insensitively after normalization.

| Outcome | Verdict |
|---|---|
| Exact case-sensitive match | PASS |
| Case-insensitive match (e.g. "DANVILLE" vs "Danville") | WARN (casing) |
| Extracted value is empty | FAIL (missing) |
| Both non-empty but mismatched | FAIL |

The casing WARN exists because some documents print mixed casing for the
same value. If casing matters for downstream use, either tighten the
field's `instructions` to enforce casing ("preserve original casing
exactly as printed") or accept the WARN.

## 3. Repeating-record (group) matching and field-level scoring

Comparing arrays of objects is harder than comparing flat dicts. The
comparator pairs records, then scores **each field within a matched
record** — never all-or-nothing:

1. For each expected record, find the extracted record with the best
   field overlap (no per-domain match key required — works for charges,
   meters, claims, line items, any repeating group).
2. If no match, mark the record `not_found` and count each value the key
   specified as a `not-found` field miss.
3. If matched, compare every field within the record. Each field gets a
   status **and a miss type** (see §3.1). A single bad field no longer
   zeroes the record: the record reports per-field detail, and group
   accuracy is computed field-by-field.
4. After matching all expected records, scan the extracted records for
   ones with no expected match — mark those `extra` (over-extraction).

This is the keystone of repeating-group accuracy. Under the old
all-or-nothing rule a meter that matched on 13 of 14 fields scored 0%;
field-level scoring reports it as ~93% and names the one field that
missed, turning an opaque `0%` into a precise iteration target.

The report carries, per group: a `field_breakdown` (per field name:
pass / scored / not_found / field_mismatch / expected_null), a
`record_summary` (matched / expected / extra / not_found), and the
summary tuples `records: (matched, expected)` and `fields: (passed,
scored)`. The batch rollup (`batch_extraction.aggregate_reports`) adds
`group_field_accuracy` (per-field-within-group across the whole set —
the precise iteration target), `group_record_coverage`, and
`group_top_misses`.

### 3.1 Miss-type classification

Every field within a matched (or not-found) record carries a `miss_type`,
so genuine extraction failures separate from non-failures:

| `miss_type` | Meaning | Counts toward accuracy? |
|---|---|---|
| `None` (clean pass) | exact or casing-only match | yes — pass |
| `expected-null` | expected-answer JSON has no value here | **no** — excluded from the denominator (informational only) |
| `not-found` | expected answer has a value; extraction produced nothing | yes — miss |
| `field-mismatch` | expected answer has a value; extraction produced a different one | yes — miss |

Legitimately-null expected-answer fields (e.g. a meter's `supplier_name` on a
direct-billed account) are **excluded** from the field-accuracy
denominator — they are not extraction targets, so they neither pass nor
fail. They are reported as `expected-null` counts separately.

The split is the triage tool. A cluster of `field-mismatch` on one field
across many records points at either a prompt problem (truncated /
non-verbatim descriptions) or an expected-answer artifact (DB-normalized
values that diverge from the printed document). A cluster of `not-found`
points at missed rows or a too-narrow prompt. `extra` records point at
over-extraction (subtotals, recap boxes, cross-chunk duplicates). See
`15_repeating_groups.md` for the prompt patterns that fix each.

### 3.2 The `extra` verdict

The `extra` verdict typically catches one of two patterns:

- The model is over-extracting subtotals/recap rows — fix by tightening
  the group-level `prompt.instructions` with explicit IS-NOT examples, or
  dedup cross-chunk duplicates with `unique_attrs` (see
  `12_business_logic.md`).
- The expected answers are incomplete — confirm with the user before changing
  the extraction.

## 4. What WARN means

WARN is not a failure. It means the field's value is acceptable but
worth flagging:

- **WARN (casing)** — string matched case-insensitively. Acceptable if
  downstream code is also case-insensitive; tighten the prompt if not.
- **WARN (value; key null)** — extraction produced a value the expected-answer JSON
  leaves null. Not a failure (extract the printed value anyway; the
  customer reconciles).

A WARN row should be either accepted with documentation or fixed in the
YAML. Do not let WARN rows accumulate silently across iterations.

## 5. Meters and other metered-usage groups

Meter groups score exactly like any other repeating group (§3): records
pair by best field overlap (no hardcoded `meter_number` key), then every
field scores individually with its miss type. Add expected meter records
under a top-level `meters` array in expected-answer JSON:

```json
{
  "meters": [
    { "meter_id": "A12345", "metered_usage_quantity": 1842 }
  ]
}
```

Spreadsheet expected answers do not have a general meter convention. Map them
into runner-shaped JSON before scoring. Spreadsheet and CSV files remain
supported as field-catalog inputs for the coverage helper, not as direct
`score_extraction.py` inputs.

## 6. Accuracy thresholds

Per-field accuracy is the primary metric: the fraction of scored fields
(singleton and within-group) whose verdict is PASS or an acceptable WARN.
For production-grade extractions the bar is ≥95% per-field PASS, with all
WARN rows explicitly accepted.

For repeating groups, read **field-level** group accuracy
(`group_field_accuracy`), not record pass/fail. The per-field breakdown
is what you iterate against: drive each field's accuracy up, and confirm
record coverage (matched vs expected, plus `extra`) separately so
over/under-extraction stays visible. A genuinely missing record (a missed
charge) shows as a `not_found` record / `docs_with_structural_failure`,
and for production billing the bar there is 0 missing records.

## 7. When to stop

Stop iterating when any of these is true:

- All FAIL rows are documented platform-side issues (see
  `6_known_limitations.md`)
- All FAIL rows are convention ambiguities the user has explicitly
  decided to accept
- Iteration is not converging — iteration N regresses or fails to
  improve over iteration N-1. See `8_iteration_and_feedback.md` §2 for
  the iteration budget and the non-convergence signal; do not tighten
  prompts further past this point.

Use `prompt-improvement-loop.md` before changing YAML: source-adjudicate the
disagreement, classify the miss, change one prompt or group rule, compile, run
or rescore, and check for regression.

Do not stop because the loop is "good enough" without recording why each
remaining FAIL or WARN is acceptable. The accuracy report is the
hand-off artifact for the user to review; it should be self-explanatory.
