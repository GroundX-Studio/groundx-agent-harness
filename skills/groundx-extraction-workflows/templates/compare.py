"""
compare.py — compare an extraction JSON against a ground-truth answer key.

Usage:
    python compare.py output.json answer_key.csv
    python compare.py output.json answer_key.json

Supports two answer-key shapes:

  1. CSV with a `CHG_CLASS` column. Rows where `CHG_CLASS=fp` describe
     statement-level fields (one row per document). Rows where `CHG_CLASS=mrc`
     or `CHG_CLASS=tax` describe individual charges (zero or more per
     document). Other CHG_CLASS values are ignored — they are subtotal rows
     used by the source system, not ground truth for individual fields.

  2. JSON with the same shape the runner produces:
       {
         "<statement field>": "...",
         ...,
         "account_charges": [ { ... }, ... ],
         "meters": [ { ... }, ... ]
       }

Output is a structured pass/warn/fail report. Exit code is 0 if every
required field passes (warnings allowed), 1 otherwise. The exit code is
intended for shell scripting and CI.
"""

import csv
import json
import os
import sys
import typing


# ── normalization ──────────────────────────────────────────────────────────

_FIELD_ALIASES: typing.Dict[str, typing.List[str]] = {
    # Charge-array hardcoded-name workaround (AGE-6). The platform requires
    # `charge_amount` and `charge_description_as_printed`; legacy answer keys
    # use `chg_amt` and `chg_desc_1`.
    "chg_desc_1": ["chg_desc_1", "charge_description_as_printed"],
    "chg_amt": ["chg_amt", "charge_amount"],
    "charge_description_as_printed": ["charge_description_as_printed", "chg_desc_1"],
    "charge_amount": ["charge_amount", "chg_amt"],
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
    for alias in _FIELD_ALIASES.get(key, [key]):
        if alias in d:
            return d[alias]
    return ""


# ── answer-key loaders ─────────────────────────────────────────────────────

_CSV_STATEMENT_FIELDS: typing.Dict[str, str] = {
    "ACCT_LEVEL_1": "acct_level_1",
    "SP_INV_NUM": "sp_inv_num",
    "INV_DATE": "inv_date",
    "DUE_DATE": "due_date",
    "PREV_BILL_AMT": "prev_bill_amt",
    "PMTS_RCVD": "pmts_rcvd",
    "PMTS_APP_THRU_DATE": "pmts_app_thru_date",
    "BAL_FWD": "bal_fwd",
    "TOT_NEW_CHGS": "tot_new_chgs",
    "TOT_AMT_DUE": "tot_amt_due",
    "TOT_MRC_CHGS": "tot_mrc_chgs",
    "TOT_TAXSUR": "tot_taxsur",
    "SP_NAME": "sp_name",
    "SP_REMIT_ADDR_1": "sp_remit_addr_1",
    "SP_REMIT_CITY": "sp_remit_city",
    "SP_REMIT_STATE": "sp_remit_state",
    "SP_REMIT_ZIP": "sp_remit_zip",
    "BILLED_COMPANY_NAME": "billed_company_name",
    "BILLED_COMPANY_ADDR_1": "billed_company_addr_1",
    "BILLED_COMPANY_CITY": "billed_company_city",
    "BILLED_COMPANY_STATE": "billed_company_state",
    "BILLED_COMPANY_ZIP": "billed_company_zip",
    "CURRENCY": "currency",
}

_CSV_CHARGE_FIELDS: typing.Dict[str, str] = {
    "CHG_DESC_1": "chg_desc_1",
    "CHG_AMT": "chg_amt",
    "SITE_A_ADDR_1": "site_a_addr_1",
    "SITE_A_ADDR_2": "site_a_addr_2",
    "SITE_A_ADDR_CITY": "site_a_addr_city",
    "SITE_A_ADDR_ST": "site_a_addr_st",
    "SITE_A_ADDR_ZIP": "site_a_addr_zip",
    "BEG_CHG_DATE": "beg_chg_date",
    "END_CHG_DATE": "end_chg_date",
}


def load_answer_key_csv(csv_path: str) -> typing.Dict[str, typing.Any]:
    expected: typing.Dict[str, typing.Any] = {"statement": {}, "charges": [], "meters": []}
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chg_class = (row.get("CHG_CLASS") or "").strip().lower()
            if chg_class == "fp":
                for csv_key, dest_key in _CSV_STATEMENT_FIELDS.items():
                    val = (row.get(csv_key) or "").strip()
                    if val:
                        expected["statement"][dest_key] = val
            elif chg_class in ("mrc", "tax"):
                charge: typing.Dict[str, str] = {}
                for csv_key, dest_key in _CSV_CHARGE_FIELDS.items():
                    val = (row.get(csv_key) or "").strip()
                    if val:
                        charge[dest_key] = val
                if charge:
                    expected["charges"].append(charge)
    return expected


def load_answer_key_json(json_path: str) -> typing.Dict[str, typing.Any]:
    with open(json_path, "r") as f:
        data = json.load(f)
    expected: typing.Dict[str, typing.Any] = {"statement": {}, "charges": [], "meters": []}
    for key, value in data.items():
        if key == "account_charges" and isinstance(value, list):
            expected["charges"] = [c for c in value if isinstance(c, dict)]
            continue
        if key == "meters" and isinstance(value, list):
            expected["meters"] = [m for m in value if isinstance(m, dict)]
            continue
        if value not in (None, "", []):
            expected["statement"][key] = value
    return expected


def load_answer_key(path: str) -> typing.Dict[str, typing.Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return load_answer_key_csv(path)
    if ext == ".json":
        return load_answer_key_json(path)
    raise ValueError(f"unsupported answer-key extension: {ext} (expected .csv or .json)")


# ── comparators ────────────────────────────────────────────────────────────


def _numeric_match(a: str, b: str) -> typing.Optional[bool]:
    try:
        return abs(float(a) - float(b)) < 0.01
    except (ValueError, TypeError):
        return None


def compare_statement(
    extracted: typing.Dict[str, typing.Any],
    expected: typing.Dict[str, typing.Any],
) -> typing.List[dict]:
    results = []
    for field, exp_val in expected.items():
        ext_val = _get_aliased(extracted, field)
        exp_norm = normalize_value(exp_val)
        ext_norm = normalize_value(ext_val)
        numeric = _numeric_match(exp_norm, ext_norm)
        if numeric is True:
            results.append({"field": field, "expected": exp_val, "extracted": ext_val, "status": "PASS"})
            continue
        if numeric is False and ext_norm != "":
            results.append({"field": field, "expected": exp_val, "extracted": ext_val, "status": "FAIL"})
            continue
        if ext_norm == "":
            results.append({"field": field, "expected": exp_val, "extracted": "(empty)", "status": "FAIL (missing)"})
            continue
        if exp_norm.lower() == ext_norm.lower():
            status = "PASS" if exp_norm == ext_norm else "WARN (casing)"
            results.append({"field": field, "expected": exp_val, "extracted": ext_val, "status": status})
        else:
            results.append({"field": field, "expected": exp_val, "extracted": ext_val, "status": "FAIL"})
    return results


def compare_charges(
    extracted_charges: typing.List[dict],
    expected_charges: typing.List[dict],
) -> typing.List[dict]:
    results = []
    for exp_charge in expected_charges:
        exp_desc = str(_get_aliased(exp_charge, "chg_desc_1") or "")
        exp_amt = _get_aliased(exp_charge, "chg_amt")

        match = None
        for ext_charge in extracted_charges:
            ext_desc = str(_get_aliased(ext_charge, "chg_desc_1") or "")
            if ext_desc and ext_desc.lower() == exp_desc.lower():
                match = ext_charge
                break

        if not match:
            results.append({
                "charge": exp_desc or "(no description)",
                "status": "FAIL (not found)",
                "details": f"Expected: {exp_desc} ${exp_amt}",
            })
            continue

        charge_pass = True
        details = []
        for field, exp_val in exp_charge.items():
            ext_val = _get_aliased(match, field)
            exp_norm = normalize_value(exp_val)
            ext_norm = normalize_value(ext_val)
            numeric = _numeric_match(exp_norm, ext_norm)
            if numeric is True:
                continue
            if numeric is False or exp_norm.lower() != ext_norm.lower():
                charge_pass = False
                details.append(f"{field}: expected '{exp_val}' got '{ext_val}'")

        if charge_pass:
            results.append({"charge": exp_desc, "status": "PASS", "details": f"${exp_amt}"})
        else:
            results.append({"charge": exp_desc, "status": "FAIL", "details": "; ".join(details)})

    expected_descs = {
        str(_get_aliased(c, "chg_desc_1") or "").lower() for c in expected_charges
    }
    for ext_charge in extracted_charges:
        ext_desc = str(_get_aliased(ext_charge, "chg_desc_1") or "")
        if ext_desc and ext_desc.lower() not in expected_descs:
            results.append({
                "charge": ext_desc,
                "status": "WARN (extra)",
                "details": f"Not in answer key: ${_get_aliased(ext_charge, 'chg_amt')}",
            })

    return results


def compare_meters(
    extracted_meters: typing.List[dict],
    expected_meters: typing.List[dict],
) -> typing.List[dict]:
    results = []
    used_indexes: set[int] = set()

    for exp_meter in expected_meters:
        exp_number = str(_get_aliased(exp_meter, "meter_number") or "")

        match = None
        match_index = -1
        for index, ext_meter in enumerate(extracted_meters):
            if index in used_indexes:
                continue
            ext_number = str(_get_aliased(ext_meter, "meter_number") or "")
            if exp_number and ext_number and ext_number.lower() == exp_number.lower():
                match = ext_meter
                match_index = index
                break
            if not exp_number and all(
                normalize_value(_get_aliased(ext_meter, field)).lower() == normalize_value(exp_val).lower()
                for field, exp_val in exp_meter.items()
            ):
                match = ext_meter
                match_index = index
                break

        if not match:
            results.append({
                "meter": exp_number or "(no meter_number)",
                "status": "FAIL (not found)",
                "details": f"Expected: {json.dumps(exp_meter, sort_keys=True, default=str)}",
            })
            continue

        used_indexes.add(match_index)
        meter_pass = True
        details = []
        for field, exp_val in exp_meter.items():
            ext_val = _get_aliased(match, field)
            exp_norm = normalize_value(exp_val)
            ext_norm = normalize_value(ext_val)
            numeric = _numeric_match(exp_norm, ext_norm)
            if numeric is True:
                continue
            if numeric is False or exp_norm.lower() != ext_norm.lower():
                meter_pass = False
                details.append(f"{field}: expected '{exp_val}' got '{ext_val}'")

        if meter_pass:
            results.append({"meter": exp_number or "(matched meter)", "status": "PASS", "details": ""})
        else:
            results.append({"meter": exp_number or "(matched meter)", "status": "FAIL", "details": "; ".join(details)})

    expected_numbers = {
        str(_get_aliased(m, "meter_number") or "").lower() for m in expected_meters
    }
    for ext_meter in extracted_meters:
        ext_number = str(_get_aliased(ext_meter, "meter_number") or "")
        if ext_number and ext_number.lower() not in expected_numbers:
            results.append({
                "meter": ext_number,
                "status": "WARN (extra)",
                "details": "Not in answer key",
            })

    return results


# ── reporting ──────────────────────────────────────────────────────────────


def _icon(status: str) -> str:
    if status == "PASS":
        return "PASS"
    if status.startswith("WARN"):
        return "WARN"
    return "FAIL"


def main(argv: typing.List[str]) -> int:
    if len(argv) != 3:
        print("usage: python compare.py <output.json> <answer_key.(csv|json)>", file=sys.stderr)
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
    extracted_charges = extracted.get("account_charges") or extracted.get("charges") or []
    extracted_meters = extracted.get("meters") or []

    print("=" * 60)
    print("EXTRACTX COMPARISON")
    print("=" * 60)
    print(
        f"answer key: {len(expected['statement'])} statement fields, "
        f"{len(expected['charges'])} charges, "
        f"{len(expected['meters'])} meters"
    )

    print("\n" + "-" * 60)
    print("STATEMENT FIELDS")
    print("-" * 60)
    stmt_results = compare_statement(extracted, expected["statement"])
    stmt_pass = sum(1 for r in stmt_results if r["status"] == "PASS")
    for r in stmt_results:
        print(f"  [{_icon(r['status'])}] {r['field']}: {r['status']}")
        if r["status"] != "PASS":
            print(f"       expected:  {r['expected']}")
            print(f"       extracted: {r['extracted']}")
    print(f"\nstatement: {stmt_pass}/{len(stmt_results)} passed")

    print("\n" + "-" * 60)
    print("CHARGES")
    print("-" * 60)
    chg_results = compare_charges(extracted_charges, expected["charges"])
    chg_pass = sum(1 for r in chg_results if r["status"] == "PASS")
    for r in chg_results:
        print(f"  [{_icon(r['status'])}] {r['charge']}: {r['status']}")
        if r.get("details") and r["status"] != "PASS":
            print(f"       {r['details']}")
    print(f"\ncharges: {chg_pass}/{len(expected['charges'])} passed")

    print("\n" + "-" * 60)
    print("METERS")
    print("-" * 60)
    meter_results = compare_meters(extracted_meters, expected["meters"])
    meter_pass = sum(1 for r in meter_results if r["status"] == "PASS")
    for r in meter_results:
        print(f"  [{_icon(r['status'])}] {r['meter']}: {r['status']}")
        if r.get("details") and r["status"] != "PASS":
            print(f"       {r['details']}")
    print(f"\nmeters: {meter_pass}/{len(expected['meters'])} passed")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  statement fields: {stmt_pass}/{len(stmt_results)}")
    print(f"  charges:          {chg_pass}/{len(expected['charges'])}")
    print(f"  meters:           {meter_pass}/{len(expected['meters'])}")

    has_failure = any(r["status"].startswith("FAIL") for r in stmt_results + chg_results + meter_results)
    return 1 if has_failure else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
