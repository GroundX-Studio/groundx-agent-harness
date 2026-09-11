"""Field policies preserve meaning without document-specific exceptions."""
import copy
import json
import hashlib
from pathlib import Path

import pytest
import score_extraction as score


def policy(fields=None):
    return {"version": 1, "profiles": {
        "currency": {"kind": "equivalence", "values": {"USD": ["USD", "currency_dollars"], "EUR": ["EUR", "currency_euros"]}},
        "customer": {"kind": "source_review", "criterion": "Same customer; incidental site labels may differ."},
    }, "fields": fields or {"items[].charges[].currency": "currency"}}


def run(expected_value, actual, **kwargs):
    return score.compare_extraction({"items": [{"id": "007", "charges": actual}]},
        {"singleton": {}, "groups": {"items": [{"id": "007", "charges": expected_value}]}},
        comparison_policy=policy(), **kwargs)


def test_nested_currency_and_numbers_preserve_raw_answers():
    expected = [{"amount": 55.0, "currency": "currency_dollars"}]
    actual = [{"amount": 55, "currency": "USD"}]
    before = copy.deepcopy(actual)
    report = run(expected, actual)
    field = report["groups"]["items"]["records"][0]["fields"][1]
    assert field["status"] == "PASS"
    assert field["raw_status"] == "FAIL"
    assert field["expected"] == expected and field["extracted"] == actual == before
    assert report["comparison"]["policy_sha256"]


@pytest.mark.parametrize("actual", [
    [{"amount": 55, "currency": "EUR"}],
    [{"amount": 56, "currency": "USD"}],
    [{"amount": 55, "currency": "$"}],
    [{"amount": True, "currency": "USD"}],
    [{"amount": "55", "currency": "USD"}],
    [],
])
def test_real_changes_do_not_pass(actual):
    assert run([{"amount": 55.0, "currency": "currency_dollars"}], actual)["has_failure"]


def test_native_json_compared_structurally_without_policy():
    assert score.compare_field([{"n": 55.0}], [{"n": 55}]) == "PASS"
    assert score.compare_field([{"n": 1}], [{"n": True}]) == "FAIL"
    assert score.compare_field([{"id": "007"}], [{"id": "7"}]) == "FAIL"
    assert score.compare_field([1, 2], [2, 1]) == "FAIL"
    assert score.compare_field([1, 1], [1]) == "FAIL"


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(version=2),
    lambda p: p["fields"].update({"items[].missing": "currency"}),
    lambda p: p["fields"].update({"items[].charges[].currency": "unknown"}),
    lambda p: p["profiles"]["currency"]["values"]["EUR"].append("usd"),
    lambda p: p["profiles"]["customer"].update(kind="fuzzy"),
])
def test_invalid_policy_rejected(mutate):
    p = policy(); mutate(p)
    with pytest.raises(ValueError):
        score.compare_extraction({"items": []}, {"singleton": {}, "groups": {"items": [{"charges": [{"currency": "USD"}]}]}}, comparison_policy=p)


def review_inputs(tmp_path):
    expected = {"singleton": {"customer": "Meadow Stores (32)"}, "groups": {}}
    actual = {"customer": "Meadow Stores"}
    p = policy({"customer": "customer"})
    from pypdf import PdfWriter
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / "source.pdf"; writer.write(str(pdf))
    schema = tmp_path / "schema.yaml"
    schema.write_text('customer: "Name of the customer receiving service."\n')
    context = {"definition_source": {"reference": str(schema), "sha256": hashlib.sha256(schema.read_bytes()).hexdigest(), "fields": {"customer": ["customer"]}}, "field_definitions": {"customer": "Name of the customer receiving service."},
               "sources": [{"sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "page": 1, "reference": str(pdf)}]}
    return actual, expected, p, context


def test_names_require_bound_review_and_never_strip_numbers(tmp_path):
    a, e, p, context = review_inputs(tmp_path)
    initial = score.compare_extraction(a, e, comparison_policy=p, review_context=context)
    assert initial["has_failure"] and initial["comparison"]["pending_reviews"] == 1
    packet = initial["comparison"]["review_packets"][0]
    decision = {"packet_sha256": packet["packet_sha256"], "decision": "equivalent",
        "reviewer": {"id": "independent-reviewer", "version": "review-1"},
        "rationale": "The source identifies one customer and an incidental site number.",
        "citations": [{"sha256": context["sources"][0]["sha256"], "page": 1}]}
    receipts = {"version": 1, "decisions": [decision]}
    report = score.compare_extraction(a, e, comparison_policy=p, review_context=context, review_decisions=receipts)
    assert report["singleton"][0]["status"] == "PASS"
    assert report["singleton"][0]["raw_status"] == "FAIL"
    assert report["comparison"]["pending_reviews"] == 0
    for altered in [dict(a, customer="Other Stores"), dict(a, extra="changed")]:
        with pytest.raises(ValueError):
            score.compare_extraction(altered, e, comparison_policy=p, review_context=context, review_decisions=receipts)
    wrong = copy.deepcopy(receipts); wrong["decisions"][0]["citations"][0]["page"] = 2
    with pytest.raises(ValueError):
        score.compare_extraction(a, e, comparison_policy=p, review_context=context, review_decisions=wrong)


def test_missing_review_context_and_nulls_never_pass(tmp_path):
    a, e, p, context = review_inputs(tmp_path)
    report = score.compare_extraction(a, e, comparison_policy=p)
    assert report["comparison"]["pending_reviews"] == 1
    assert not report["comparison"]["review_packets"][0]["reviewable"]
    missing = score.compare_extraction({"customer": None}, e, comparison_policy=p, review_context=context)
    assert missing["has_failure"]
    assert not missing["comparison"]["review_packets"]


@pytest.mark.parametrize("defect", ["page", "pdf", "schema", "definition"])
def test_declared_evidence_is_verified(tmp_path, defect):
    a, e, p, context = review_inputs(tmp_path)
    if defect == "page":
        context["sources"][0]["page"] = 999
    elif defect == "pdf":
        context["sources"][0]["sha256"] = "0" * 64
    elif defect == "schema":
        context["definition_source"]["sha256"] = "0" * 64
    else:
        context["field_definitions"]["customer"] = "Invented rule."
    with pytest.raises(ValueError):
        score.compare_extraction(a, e, comparison_policy=p, review_context=context)


def test_batch_keeps_pending_packets_and_raw_values(tmp_path, monkeypatch):
    import batch_score
    a, e, p, context = review_inputs(tmp_path)
    for folder in ("keys", "contexts", "run", "out"):
        (tmp_path / folder).mkdir()
    (tmp_path / "keys/doc.json").write_text(json.dumps(e["singleton"]))
    (tmp_path / "run/doc.extracted.json").write_text(json.dumps(a))
    (tmp_path / "contexts/doc.json").write_text(json.dumps(context))
    (tmp_path / "policy.json").write_text(json.dumps(p))
    monkeypatch.setattr("sys.argv", ["batch_score", str(tmp_path / "run"), "--keys-dir", str(tmp_path / "keys"), "--out", str(tmp_path / "out"), "--comparison-policy", str(tmp_path / "policy.json"), "--review-context-dir", str(tmp_path / "contexts")])
    assert batch_score.main() == 1
    report = json.loads((tmp_path / "out/doc.accuracy.json").read_text())
    assert report["pending_reviews"] == 1
    detail = report["comparison_report"]
    assert detail["singleton"][0]["raw_status"] == "FAIL"
    assert detail["comparison"]["review_packets"][0]["extracted"] == a["customer"]
    assert json.loads((tmp_path / "out/aggregated.accuracy.json").read_text())["pending_reviews"] == 1
