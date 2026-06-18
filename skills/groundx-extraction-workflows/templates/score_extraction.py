"""
score_extraction.py — compare an extraction JSON against a ground-truth answer key.

Usage:
    python score_extraction.py output.json answer_key.json
    python score_extraction.py final_output.json answer_key.json

Domain-agnostic comparison
--------------------------
The comparator discovers structure from the data, not from hardcoded group
names: scalar answer-key keys are compared as singleton (per-document) fields;
list-valued keys are compared as repeating record groups. Records are paired by
best field overlap (no per-domain match key required). Group names are aligned
across the answer key and the extraction, with a small alias map for known
renames (e.g. answer-key `charges` ↔ runner `account_charges`).

Null-vs-miss
------------
A field the answer key leaves null is distinguished from an extraction miss:
  - expected null + extracted null    → PASS (correct null)
  - expected null + extracted a value  → WARN (value present; key null) — NOT a
    failure (e.g. AGE-86 customer_account_id: extract the printed value anyway)
  - expected a value + extracted null  → FAIL (missing)

Answer-key format: JSON in the runner's output shape — scalar keys → singleton
(per-document) fields (null kept, so null-vs-miss can be scored), list-valued
keys → record groups. Convert other answer-key formats to this shape first.

Output is a structured pass/warn/fail report with per-group accuracy. Exit code
is 0 if no field fails (warnings allowed), 1 otherwise.
"""

import csv
import json
import os
import sys
import typing


# ── normalization ──────────────────────────────────────────────────────────

# Group-name aliases: answer-key group name → names it may appear under in the
# extraction. Mirrors the field-alias pattern; Component 5 (final_value renames)
# will generalize this into the YAML.
_GROUP_ALIASES: typing.Dict[str, typing.List[str]] = {
    "charges": ["charges", "account_charges"],
    "account_charges": ["account_charges", "charges"],
}


def normalize_value(val: typing.Any) -> str:
    """Normalize a value for comparison: strip whitespace, normalize dates."""
    if val is None:
        return ""
    s = str(val).strip()
    if "/" in s and len(s) <= 10:
        parts = s.split("/")
        if len(parts) == 3:
            m, d, y = parts
            if len(y) == 4 and m.isdigit() and d.isdigit():
                s = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return s


def _get_aliased(d: typing.Dict[str, typing.Any], key: str) -> typing.Any:
    # Field names in the answer key are expected to match the extraction's
    # field names (both derive from the YAML). No client-specific bridging.
    if key in d:
        return d.get(key, "")
    if "." not in key:
        return ""
    current: typing.Any = d
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return ""
        current = current.get(part)
    return current


def _resolve_group(extracted: typing.Dict[str, typing.Any], group_name: str) -> typing.List[dict]:
    """Find the extracted record list for an answer-key group, honoring aliases."""
    for alias in _GROUP_ALIASES.get(group_name, [group_name]):
        value = extracted.get(alias)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


# ── answer-key loader ───────────────────────────────────────────────────────


def _empty_expected() -> typing.Dict[str, typing.Any]:
    """Normalized answer-key structure: singleton fields + named record groups."""
    return {"singleton": {}, "groups": {}}


def load_answer_key_json(json_path: str) -> typing.Dict[str, typing.Any]:
    with open(json_path, "r") as f:
        data = json.load(f)
    expected = _empty_expected()
    for key, value in data.items():
        if isinstance(value, list):
            expected["groups"][key] = [r for r in value if isinstance(r, dict)]
        elif isinstance(value, dict):
            # Nested object: treat its scalars as namespaced singleton fields.
            for sub_key, sub_val in value.items():
                if not isinstance(sub_val, (list, dict)):
                    expected["singleton"][f"{key}.{sub_key}"] = sub_val
        else:
            # Scalar — keep even when null so null-vs-miss can be checked.
            expected["singleton"][key] = value
    return expected


def load_answer_key(path: str) -> typing.Dict[str, typing.Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return load_answer_key_json(path)
    raise ValueError(
        f"unsupported answer-key extension: {ext} (expected .json). "
        f"Convert other formats (e.g. CSV) to the runner's JSON output shape first."
    )


# ── comparators ────────────────────────────────────────────────────────────


def _numeric_match(a: str, b: str) -> typing.Optional[bool]:
    try:
        return abs(float(a) - float(b)) < 0.01
    except (ValueError, TypeError):
        return None


def compare_field(exp_val: typing.Any, ext_val: typing.Any) -> str:
    """Compare one field's expected vs extracted value with null-vs-miss semantics."""
    exp_norm = normalize_value(exp_val)
    ext_norm = normalize_value(ext_val)

    if exp_norm == "":
        # Answer key has no value for this field.
        if ext_norm == "":
            return "PASS"  # correct null
        return "WARN (value; key null)"  # extracted a value the key leaves null
    if ext_norm == "":
        return "FAIL (missing)"

    numeric = _numeric_match(exp_norm, ext_norm)
    if numeric is True:
        return "PASS"
    if numeric is False:
        return "FAIL"
    if exp_norm.lower() == ext_norm.lower():
        return "PASS" if exp_norm == ext_norm else "WARN (casing)"
    return "FAIL"


def classify_field(exp_val: typing.Any, ext_val: typing.Any) -> typing.Tuple[str, typing.Optional[str]]:
    """Return (status, miss_type) for one field within a record.

    miss_type classifies why a field is not a clean extraction hit:
      - "expected-null":  the answer key has no value here (informational, NOT
        an extraction target — excluded from the field-accuracy denominator).
      - "not-found":      key has a value; extraction produced nothing.
      - "field-mismatch": key has a value; extraction produced a different one.
      - None:             clean pass (exact or casing-only).
    """
    status = compare_field(exp_val, ext_val)
    if normalize_value(exp_val) == "":
        return status, "expected-null"
    if status in ("PASS", "WARN (casing)"):
        return status, None
    if normalize_value(ext_val) == "":
        return status, "not-found"
    return status, "field-mismatch"


def compare_singleton(
    extracted: typing.Dict[str, typing.Any],
    expected_singleton: typing.Dict[str, typing.Any],
) -> typing.List[dict]:
    results = []
    for field, exp_val in expected_singleton.items():
        ext_val = _get_aliased(extracted, field)
        status = compare_field(exp_val, ext_val)
        results.append({
            "field": field,
            "expected": exp_val,
            "extracted": ext_val if normalize_value(ext_val) != "" else "(empty)",
            "status": status,
        })
    return results


def _record_overlap(exp_record: dict, ext_record: dict) -> int:
    """How many of the expected record's fields match the extracted record."""
    score = 0
    for field, exp_val in exp_record.items():
        if normalize_value(exp_val) == "":
            continue
        if compare_field(exp_val, _get_aliased(ext_record, field)) in ("PASS", "WARN (casing)"):
            score += 1
    return score


def _record_label(record: dict) -> str:
    for key in ("meter_number", "charge_description_as_printed", "chg_desc_1", "description", "desc", "id"):
        val = _get_aliased(record, key)
        if normalize_value(val):
            return str(val)
    # Fall back to the first non-empty value.
    for val in record.values():
        if normalize_value(val):
            return str(val)
    return "(record)"


def _empty_field_counts() -> typing.Dict[str, int]:
    return {"pass": 0, "scored": 0, "not_found": 0, "field_mismatch": 0, "expected_null": 0}


def compare_records(
    extracted_records: typing.List[dict],
    expected_records: typing.List[dict],
) -> typing.Dict[str, typing.Any]:
    """Pair expected and extracted records by best field overlap, then score
    each field WITHIN the matched records — never all-or-nothing.

    Returns a dict with:
      - records:         per-record results (matched / not_found / extra), each
                         matched record carrying its per-field statuses + miss types.
      - field_breakdown: per field name, aggregated counts across the group's
                         records (pass / scored / not_found / field_mismatch /
                         expected_null). Field accuracy = pass / scored; nulls
                         are excluded from `scored`.
      - record_summary:  matched / expected / extra / not_found record counts.
      - field_summary:   (passed, scored) across the whole group.
    """
    records_out: typing.List[dict] = []
    field_breakdown: typing.Dict[str, typing.Dict[str, int]] = {}
    used: set[int] = set()
    matched = not_found = 0

    def bump(field: str, key: str) -> None:
        field_breakdown.setdefault(field, _empty_field_counts())[key] += 1

    for exp_record in expected_records:
        best_idx = -1
        best_score = 0
        for idx, ext_record in enumerate(extracted_records):
            if idx in used:
                continue
            score = _record_overlap(exp_record, ext_record)
            if score > best_score:
                best_score = score
                best_idx = idx

        label = _record_label(exp_record)
        if best_idx < 0 or best_score == 0:
            not_found += 1
            # Every value the key specified is a not-found field on this record.
            for field, exp_val in exp_record.items():
                if normalize_value(exp_val) == "":
                    bump(field, "expected_null")
                else:
                    bump(field, "scored")
                    bump(field, "not_found")
            records_out.append({
                "label": label,
                "match": "not_found",
                "details": f"Expected: {json.dumps(exp_record, sort_keys=True, default=str)}",
            })
            continue

        used.add(best_idx)
        matched += 1
        match = extracted_records[best_idx]
        fields: typing.List[dict] = []
        record_ok = True
        for field, exp_val in exp_record.items():
            ext_val = _get_aliased(match, field)
            status, miss_type = classify_field(exp_val, ext_val)
            if miss_type == "expected-null":
                bump(field, "expected_null")
            else:
                bump(field, "scored")
                if miss_type is None:
                    bump(field, "pass")
                else:
                    bump(field, miss_type.replace("-", "_"))
                    record_ok = False
            fields.append({
                "field": field,
                "expected": exp_val,
                "extracted": ext_val if normalize_value(ext_val) != "" else "(empty)",
                "status": status,
                "miss_type": miss_type,
            })
        records_out.append({
            "label": label,
            "match": "matched",
            "record_status": "PASS" if record_ok else "FAIL",
            "fields": fields,
        })

    extra = 0
    for idx, ext_record in enumerate(extracted_records):
        if idx not in used:
            extra += 1
            records_out.append({
                "label": _record_label(ext_record),
                "match": "extra",
                "details": "Not in answer key",
            })

    passed = sum(c["pass"] for c in field_breakdown.values())
    scored = sum(c["scored"] for c in field_breakdown.values())
    return {
        "records": records_out,
        "field_breakdown": field_breakdown,
        "record_summary": {
            "matched": matched,
            "expected": len(expected_records),
            "extra": extra,
            "not_found": not_found,
        },
        "field_summary": (passed, scored),
    }


def compare_extraction(
    extracted: typing.Dict[str, typing.Any],
    expected: typing.Dict[str, typing.Any],
) -> typing.Dict[str, typing.Any]:
    """Compare an extraction dict against a normalized answer-key structure.

    Returns a report: per-field singleton results, per-group record results, a
    summary of (pass, total) per section, and an overall has_failure flag.
    """
    singleton_results = compare_singleton(extracted, expected.get("singleton") or {})

    group_results: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    group_summary: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    group_has_failure = False
    for group_name, exp_records in (expected.get("groups") or {}).items():
        ext_records = _resolve_group(extracted, group_name)
        gr = compare_records(ext_records, exp_records)
        group_results[group_name] = gr
        rs = gr["record_summary"]
        group_summary[group_name] = {
            "records": (rs["matched"], rs["expected"]),
            "fields": gr["field_summary"],
            "extra": rs["extra"],
        }
        if rs["not_found"] or any(
            c["not_found"] or c["field_mismatch"] for c in gr["field_breakdown"].values()
        ):
            group_has_failure = True

    singleton_pass = sum(1 for r in singleton_results if r["status"] in ("PASS", "WARN (casing)", "WARN (value; key null)"))
    has_failure = group_has_failure or any(
        r["status"].startswith("FAIL") for r in singleton_results
    )

    return {
        "singleton": singleton_results,
        "groups": group_results,
        "summary": {
            "singleton": (singleton_pass, len(singleton_results)),
            "groups": group_summary,
        },
        "has_failure": has_failure,
    }


# ── scoring-input helpers (answer-key + manifest resolution) ────────────────


def load_manifest(path: typing.Optional[str]) -> typing.Dict[str, typing.Dict[str, str]]:
    """Parse a manifest CSV (a `filename` column + any dimension columns such as
    `vendor`/`service_type`) into {doc_base: {dimension: value}}. Empty if absent."""
    if not path or not os.path.isfile(path):
        return {}
    out: typing.Dict[str, typing.Dict[str, str]] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            fname = (row.get("filename") or "").strip()
            if not fname:
                continue
            base = os.path.splitext(os.path.basename(fname))[0]
            out[base] = {k: v for k, v in row.items() if k != "filename" and v}
    return out


def find_answer_key(keys_dir: str, doc_base: str) -> typing.Optional[str]:
    """Resolve a document's answer key by base name (.json / .answer.json / .answer_key.json)."""
    for cand in (f"{doc_base}.json", f"{doc_base}.answer.json", f"{doc_base}.answer_key.json"):
        p = os.path.join(keys_dir, cand)
        if os.path.isfile(p):
            return p
    return None


# ── reporting ──────────────────────────────────────────────────────────────


def _icon(status: str) -> str:
    if status == "PASS":
        return "PASS"
    if status.startswith("WARN"):
        return "WARN"
    return "FAIL"


def main(argv: typing.List[str]) -> int:
    if len(argv) != 3:
        print("usage: python score_extraction.py <extraction.json> <answer_key.json>", file=sys.stderr)
        return 2

    extract_path, key_path = argv[1], argv[2]
    if not os.path.isfile(extract_path):
        print(f"ERROR: extraction JSON not found: {extract_path}", file=sys.stderr)
        return 2
    if not os.path.isfile(key_path):
        print(f"ERROR: answer key not found: {key_path}", file=sys.stderr)
        return 2

    with open(extract_path, "r") as f:
        extracted = json.load(f)

    expected = load_answer_key(key_path)
    report = compare_extraction(extracted, expected)

    print("=" * 60)
    print("EXTRACTX COMPARISON")
    print("=" * 60)
    group_desc = ", ".join(
        f"{n}={len(v)}" for n, v in (expected.get("groups") or {}).items()
    ) or "(none)"
    print(f"answer key: {len(expected['singleton'])} singleton fields, groups: {group_desc}")

    print("\n" + "-" * 60)
    print("SINGLETON FIELDS")
    print("-" * 60)
    for r in report["singleton"]:
        print(f"  [{_icon(r['status'])}] {r['field']}: {r['status']}")
        if r["status"].startswith("FAIL"):
            print(f"       expected:  {r['expected']}")
            print(f"       extracted: {r['extracted']}")
    sp, st = report["summary"]["singleton"]
    print(f"\nsingleton: {sp}/{st} passed")

    for group_name, gr in report["groups"].items():
        print("\n" + "-" * 60)
        print(group_name.upper())
        print("-" * 60)
        for r in gr["records"]:
            if r["match"] == "matched":
                print(f"  [{_icon(r['record_status'])}] {r['label']}: {r['record_status']}")
                for f in r["fields"]:
                    if f["miss_type"] in ("not-found", "field-mismatch"):
                        print(f"       {f['field']}: expected '{f['expected']}' "
                              f"got '{f['extracted']}' [{f['miss_type']}]")
            elif r["match"] == "not_found":
                print(f"  [FAIL] {r['label']}: not found in extraction")
            else:
                print(f"  [WARN] {r['label']}: extra (not in answer key)")

        print(f"\n  per-field accuracy ({group_name}):")
        for fname, c in sorted(gr["field_breakdown"].items()):
            if not c["scored"]:
                continue
            extra = ""
            if c["pass"] < c["scored"]:
                extra = f"  [{c['not_found']} not-found, {c['field_mismatch']} mismatch]"
            print(f"    {fname}: {c['pass']}/{c['scored']} ({c['pass'] / c['scored']:.0%}){extra}")

        gs = report["summary"]["groups"][group_name]
        fp, ft = gs["fields"]
        rm, re_ = gs["records"]
        print(f"\n{group_name}: {fp}/{ft} fields, {rm}/{re_} records matched, {gs['extra']} extra")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  singleton fields: {sp}/{st}")
    for group_name, gs in report["summary"]["groups"].items():
        fp, ft = gs["fields"]
        rm, re_ = gs["records"]
        pct = f" ({fp / ft:.0%})" if ft else ""
        print(f"  {group_name}: {fp}/{ft} fields{pct}, {rm}/{re_} records")

    return 1 if report["has_failure"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
