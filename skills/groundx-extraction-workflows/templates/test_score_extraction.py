"""Contract tests for score_extraction (scoring + the aggregate rollup).

Run: python -m pytest templates/test_score_extraction.py -q

Asserts score_extraction.py:
  - scores arbitrary nested record groups (not just statement/charges/meters),
  - scores per-field WITHIN repeating records (not all-or-nothing) + miss types,
  - distinguishes a legitimately null answer-key field from an extraction miss,
  - does not penalize extracting a value the answer key leaves null,
  - pairs records without per-domain hardcoded match keys,
  - loads JSON answer keys (keeping nulls) and rejects non-JSON formats,
  - aggregate_reports rolls per-doc reports into a consolidated field-level report.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import score_extraction as compare  # noqa: E402


def _statuses(field_results):
    return {r["field"]: r["status"] for r in field_results}


def test_arbitrary_group_is_scored():
    expected = {"singleton": {}, "groups": {"claims": [{"claim_id": "A1", "amount": "10.00"}]}}
    extracted = {"claims": [{"claim_id": "A1", "amount": "10.00"}]}
    report = compare.compare_extraction(extracted, expected)
    assert "claims" in report["groups"]
    assert report["summary"]["groups"]["claims"]["records"] == (1, 1)
    assert report["summary"]["groups"]["claims"]["fields"] == (2, 2)
    assert report["has_failure"] is False


def test_null_expected_and_null_extracted_is_match_not_miss():
    expected = {"singleton": {"bill_reference_id": None}, "groups": {}}
    extracted = {"bill_reference_id": None}
    report = compare.compare_extraction(extracted, expected)
    st = _statuses(report["singleton"])
    assert st["bill_reference_id"] == "PASS"
    assert report["has_failure"] is False


def test_nested_singleton_group_scores_against_nested_extraction():
    expected = {
        "singleton": {
            "statement.sp_inv_num": "UTIL-2026-0007",
            "statement.budget_plan_name": None,
        },
        "groups": {},
    }
    extracted = {
        "statement": {
            "sp_inv_num": "UTIL-2026-0007",
            "budget_plan_name": None,
        }
    }

    report = compare.compare_extraction(extracted, expected)
    st = _statuses(report["singleton"])
    assert st["statement.sp_inv_num"] == "PASS"
    assert st["statement.budget_plan_name"] == "PASS"
    assert report["has_failure"] is False


def test_json_answer_key_field_value_objects_score_as_nested_singletons(tmp_path):
    key_path = tmp_path / "adp-shaped-answer.json"
    key_path.write_text(
        """
{
  "employer_information": {
    "employer_name": {
      "value": "Z&N Coffeehouse Companies Inc",
      "_raw_text": null,
      "_confidence": "yellow"
    },
    "address_state": {
      "value": "CO",
      "_raw_text": null,
      "_confidence": "yellow"
    }
  },
  "plan_information": {
    "plan_number": {
      "value": "001",
      "_raw_text": "Plan Sequence Number 001",
      "_confidence": "green"
    }
  }
}
""",
        encoding="utf-8",
    )
    expected = compare.load_answer_key(str(key_path))
    extracted = {
        "employer_information": {
            "employer_name": "Z&N Coffeehouse Companies Inc",
            "address_state": "CO",
        },
        "plan_information": {
            "plan_number": "001",
        },
    }

    report = compare.compare_extraction(extracted, expected)

    assert expected["singleton"] == {
        "employer_information.employer_name": "Z&N Coffeehouse Companies Inc",
        "employer_information.address_state": "CO",
        "plan_information.plan_number": "001",
    }
    assert report["summary"]["singleton"] == (3, 3)
    assert report["has_failure"] is False


def test_expected_value_but_missing_extraction_is_miss():
    expected = {"singleton": {"payment_amount_due": "312.47"}, "groups": {}}
    extracted = {"payment_amount_due": ""}
    report = compare.compare_extraction(extracted, expected)
    st = _statuses(report["singleton"])
    assert st["payment_amount_due"].startswith("FAIL")
    assert report["has_failure"] is True


def test_value_when_answer_key_is_null_is_not_a_failure():
    # AGE-86: extract the printed account number even when the answer key is
    # null; the customer reconciles. Must not count as a failure.
    expected = {"singleton": {"customer_account_id": None}, "groups": {}}
    extracted = {"customer_account_id": "4001234567"}
    report = compare.compare_extraction(extracted, expected)
    st = _statuses(report["singleton"])
    assert not st["customer_account_id"].startswith("FAIL")
    assert report["has_failure"] is False


def test_records_pair_without_hardcoded_match_key():
    # Two records that pair by best field overlap, in arbitrary order, in a
    # group whose name is not charges/meters.
    expected = {"singleton": {}, "groups": {"line_items": [
        {"desc": "Distribution", "amt": "148.22"},
        {"desc": "Transmission", "amt": "87.36"},
    ]}}
    extracted = {"line_items": [
        {"desc": "Transmission", "amt": "87.36"},
        {"desc": "Distribution", "amt": "148.22"},
    ]}
    report = compare.compare_extraction(extracted, expected)
    assert report["summary"]["groups"]["line_items"]["records"] == (2, 2)
    assert report["summary"]["groups"]["line_items"]["fields"] == (4, 4)
    assert report["has_failure"] is False


def test_group_name_alias_charges_account_charges():
    # Answer key says `charges`; xray_to_extract emits `account_charges`.
    expected = {"singleton": {}, "groups": {"charges": [{"desc": "Tax", "amt": "5.00"}]}}
    extracted = {"account_charges": [{"desc": "Tax", "amt": "5.00"}]}
    report = compare.compare_extraction(extracted, expected)
    assert report["summary"]["groups"]["charges"]["records"] == (1, 1)


def test_scoring_uses_final_groups_not_extra_pseudo_workflow_groups():
    expected = {
        "singleton": {},
        "groups": {
            "statement": [{"account_number": "A1", "total_due": "10.00"}],
        },
    }
    extracted = {
        "statement": [{"account_number": "A1", "total_due": "10.00"}],
        "statement_identity": [{"account_number": "A1"}],
        "statement_totals": [{"total_due": "10.00"}],
    }
    report = compare.compare_extraction(extracted, expected)
    assert set(report["groups"]) == {"statement"}
    assert report["summary"]["groups"]["statement"]["fields"] == (2, 2)
    assert report["has_failure"] is False


def test_repeating_record_scores_per_field_not_all_or_nothing():
    # The keystone: a meter that matches the answer key on every field except
    # one (service_address carries a DB-normalized value) must NOT score 0% —
    # it scores per-field. Legitimately-null key fields are excluded from the
    # denominator (reported as expected-null), not counted as passes.
    expected = {"singleton": {}, "groups": {"meters": [{
        "meter_id": "M1",
        "metered_usage_quantity": "232",
        "usage_unit_of_measure": "therms",
        "meter_service_address": "4351 Highway 12 SE",   # key (DB-normalized)
        "supplier_name": None,                            # legit null
        "market_role": None,                              # legit null
    }]}}
    extracted = {"meters": [{
        "meter_id": "M1",
        "metered_usage_quantity": "232",
        "usage_unit_of_measure": "therms",
        "meter_service_address": "12620 Vincent Ave",     # printed (mismatch)
    }]}
    report = compare.compare_extraction(extracted, expected)
    fp, ft = report["summary"]["groups"]["meters"]["fields"]
    assert ft == 4          # 4 non-null fields scored; 2 nulls excluded
    assert fp == 3          # 3/4 correct — NOT zeroed by the one mismatch
    gr = report["groups"]["meters"]
    fb = gr["field_breakdown"]
    assert fb["meter_service_address"]["field_mismatch"] == 1
    assert fb["supplier_name"]["expected_null"] == 1
    assert fb["supplier_name"]["scored"] == 0
    sa = next(f for f in gr["records"][0]["fields"] if f["field"] == "meter_service_address")
    assert sa["miss_type"] == "field-mismatch"


def test_field_miss_types_not_found_and_expected_null():
    expected = {"singleton": {}, "groups": {"meters": [
        {"meter_id": "M1", "metered_usage_quantity": "100", "note": None},
    ]}}
    extracted = {"meters": [{"meter_id": "M1"}]}   # usage missing entirely
    report = compare.compare_extraction(extracted, expected)
    gr = report["groups"]["meters"]
    fb = gr["field_breakdown"]
    assert fb["metered_usage_quantity"]["not_found"] == 1
    assert fb["meter_id"]["pass"] == 1
    assert fb["note"]["expected_null"] == 1
    assert report["summary"]["groups"]["meters"]["fields"] == (1, 2)


def test_unmatched_expected_record_is_not_found_with_field_counts():
    expected = {"singleton": {}, "groups": {"meters": [
        {"meter_id": "M1", "usage": "100"},
        {"meter_id": "M2", "usage": "200"},
    ]}}
    extracted = {"meters": [{"meter_id": "M1", "usage": "100"}]}  # M2 absent
    report = compare.compare_extraction(extracted, expected)
    gr = report["groups"]["meters"]
    assert gr["record_summary"]["not_found"] == 1
    assert gr["record_summary"]["matched"] == 1
    # M2's two non-null fields counted as not-found, scored
    assert report["summary"]["groups"]["meters"]["fields"] == (2, 4)
    assert report["has_failure"] is True


def test_json_answer_key_keeps_nulls_and_groups():
    import json, tempfile
    key = {"total": "10.00", "bill_ref": None, "charges": [{"desc": "Tax", "amt": "5.00"}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(key, f); path = f.name
    expected = compare.load_answer_key(path)
    assert expected["singleton"]["total"] == "10.00"
    assert "bill_ref" in expected["singleton"]  # null kept for null-vs-miss
    assert expected["groups"]["charges"] == [{"desc": "Tax", "amt": "5.00"}]


def test_non_json_answer_key_rejected():
    import pytest
    with pytest.raises(ValueError):
        compare.load_answer_key("answers.csv")


# ── scoring-input helpers (moved here with the functions) ────────────────────


def test_load_manifest_parses_dimensions(tmp_path):
    m = tmp_path / "m.csv"
    m.write_text("filename,vendor,service_type\ngas_01.pdf,CenterPoint,gas\nwater_01.pdf,Aqua,water\n")
    out = compare.load_manifest(str(m))
    assert out["gas_01"] == {"vendor": "CenterPoint", "service_type": "gas"}
    assert out["water_01"]["service_type"] == "water"


def test_load_manifest_missing_returns_empty():
    assert compare.load_manifest(None) == {}
    assert compare.load_manifest("/no/such/file.csv") == {}


def test_find_answer_key_variants(tmp_path):
    (tmp_path / "bill_01.json").write_text("{}")
    assert compare.find_answer_key(str(tmp_path), "bill_01") == str(tmp_path / "bill_01.json")
    assert compare.find_answer_key(str(tmp_path), "missing") is None
