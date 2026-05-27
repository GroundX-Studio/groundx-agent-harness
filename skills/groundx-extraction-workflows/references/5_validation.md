# 5. Validation

How the comparison harness scores extraction output against ground truth,
and how to read its report.

## 1. The compare loop

The comparator (`skills/groundx-extraction-workflows/templates/compare.py`) reads the
extracted JSON and the ground truth (CSV or JSON) and emits a
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
  ✅ Classic Cable - Bulk: PASS  ($36.75)
  ✅ Franchise Fee: PASS  ($1.84)
  ✅ FCC Regulatory Fee: PASS  ($0.40)

Charges: 3/3 passed

============================================================
SUMMARY
============================================================
  Statement fields: 22/23
  Charges:          3/3
```

PASS is the goal. WARN means a known-acceptable discrepancy. FAIL means
the field needs a tighter prompt or escalation.

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

## 3. Charges array matching

Comparing arrays of objects is harder than comparing flat dicts. The
comparator uses **description matching**:

1. For each expected record, find the extracted record whose
   `charge_description_as_printed` (or `chg_desc_1` alias) matches
   case-insensitively.
2. If no match, mark `FAIL (not found)`.
3. If matched, compare every field within the record. If any field
   mismatches, mark the whole record FAIL with the per-field details.
4. After matching all expected records, scan the extracted records for
   ones whose description does not appear in the ground truth — mark
   those as `WARN (extra)`.

The `WARN (extra)` verdict typically catches one of two patterns:

- The model is over-extracting subtotals — fix by tightening the
  group-level `prompt.instructions` on the `charges` group with explicit
  IS-NOT examples
- The ground truth is incomplete — confirm with the user before changing
  the extraction

## 4. What WARN means

WARN is not a failure. It means the field's value is acceptable but
worth flagging:

- **WARN (casing)** — string matched case-insensitively. Acceptable if
  downstream code is also case-insensitive; tighten the prompt if not.
- **WARN (extra)** — a charge in the extraction is not in the ground
  truth. Acceptable if the ground truth is known to be incomplete;
  otherwise an over-extraction.

A WARN row should be either accepted with documentation or fixed in the
YAML. Do not let WARN rows accumulate silently across iterations.

## 5. Accuracy thresholds

Per-field accuracy is the primary metric: the fraction of fields whose
verdict is PASS or WARN (acceptable). For production-grade extractions
the bar is ≥95% per-field PASS, with all WARN rows explicitly accepted.

Per-record accuracy applies to charges-style groups: the fraction of
expected records whose verdict is PASS. For production billing
extractions the bar is 100% — a missing record is a missed charge.

## 6. When to stop

Stop iterating when any of these is true:

- All FAIL rows are documented platform-side issues (see
  `6_known_limitations.md`)
- All FAIL rows are convention ambiguities the user has explicitly
  decided to accept
- Iteration is not converging — iteration N regresses or fails to
  improve over iteration N-1. See `8_iteration_and_feedback.md` §2 for
  the iteration budget and the non-convergence signal; do not tighten
  prompts further past this point.

Do not stop because the loop is "good enough" without recording why each
remaining FAIL or WARN is acceptable. The accuracy report is the
hand-off artifact for the user to review; it should be self-explanatory.
