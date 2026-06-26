"""Unit tests for score.py — offline batch scoring of a captured run (no API).

Run: python -m pytest templates/test_score.py -q
Builds a tiny captured run dir + answer keys and asserts score.py writes the
per-doc and aggregated reports with the right numbers.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_score as score


def _write(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def test_score_run_writes_per_doc_and_aggregated(tmp_path, monkeypatch, capsys):
    run = tmp_path / "run"
    keys = tmp_path / "keys"
    run.mkdir()
    keys.mkdir()
    # one bill: extraction matches the key on total, misses due_date
    _write(run / "bill_a.extracted.json", {"total": "10.00", "due_date": ""})
    _write(keys / "bill_a.json", {"total": "10.00", "due_date": "2026-06-15"})

    monkeypatch.setattr(sys, "argv", ["score.py", str(run), "--keys-dir", str(keys)])
    rc = score.main()
    assert rc == 0

    per_doc = json.load(open(run / "bill_a.accuracy.json"))
    assert per_doc["field_accuracy"]["total"]["accuracy"] == 1.0
    assert per_doc["field_accuracy"]["due_date"]["accuracy"] == 0.0

    agg = json.load(open(run / "aggregated.accuracy.json"))
    assert agg["documents"] == 1
    assert agg["overall_accuracy"] == 0.5  # 1 of 2 singleton fields


def test_score_run_no_docs_returns_error(tmp_path, monkeypatch):
    run = tmp_path / "run"
    keys = tmp_path / "keys"
    run.mkdir()
    keys.mkdir()
    monkeypatch.setattr(sys, "argv", ["score.py", str(run), "--keys-dir", str(keys)])
    assert score.main() == 2


def test_score_run_requires_explicit_final_output_artifact_kind(tmp_path, monkeypatch):
    run = tmp_path / "run"
    keys = tmp_path / "keys"
    run.mkdir()
    keys.mkdir()
    _write(run / "bill_a.final_output.json", {"total": "10.00"})
    _write(keys / "bill_a.json", {"total": "10.00"})

    monkeypatch.setattr(sys, "argv", ["score.py", str(run), "--keys-dir", str(keys)])
    assert score.main() == 2

    monkeypatch.setattr(
        sys,
        "argv",
        ["score.py", str(run), "--keys-dir", str(keys), "--artifact-kind", "final"],
    )
    assert score.main() == 0


# ── aggregate_reports (the batch rollup, moved here with the function) ───────


def _agg_report(singleton, groups=None):
    return {"singleton": singleton, "groups": groups or {}, "summary": {}, "has_failure": False}


def test_agg_field_accuracy_and_top_misses():
    per_doc = [
        {"doc": "a", "report": _agg_report([
            {"field": "total", "status": "PASS"},
            {"field": "due_date", "status": "FAIL (missing)"},
        ])},
        {"doc": "b", "report": _agg_report([
            {"field": "total", "status": "PASS"},
            {"field": "due_date", "status": "FAIL"},
        ])},
    ]
    agg = score.aggregate_reports(per_doc)
    assert agg["documents"] == 2
    assert agg["field_accuracy"]["total"]["accuracy"] == 1.0
    assert agg["field_accuracy"]["due_date"]["accuracy"] == 0.0
    assert agg["top_misses"][0] == {"field": "due_date", "miss_docs": 2}


def test_agg_null_vs_miss_counts_as_hit():
    per_doc = [{"doc": "a", "report": _agg_report([
        {"field": "bill_ref", "status": "WARN (value; key null)"},
        {"field": "acct", "status": "WARN (casing)"},
    ])}]
    agg = score.aggregate_reports(per_doc)
    assert agg["overall_accuracy"] == 1.0


def _agg_group(field_breakdown, record_summary):
    passed = sum(c["pass"] for c in field_breakdown.values())
    scored = sum(c["scored"] for c in field_breakdown.values())
    return {
        "records": [],
        "field_breakdown": field_breakdown,
        "record_summary": record_summary,
        "field_summary": (passed, scored),
    }


def test_agg_group_field_accuracy_and_structural_failure():
    groups = {"charges": _agg_group(
        field_breakdown={
            "amt": {"pass": 1, "scored": 2, "not_found": 1, "field_mismatch": 0, "expected_null": 0},
            "desc": {"pass": 2, "scored": 2, "not_found": 0, "field_mismatch": 0, "expected_null": 0},
        },
        record_summary={"matched": 1, "expected": 2, "extra": 0, "not_found": 1},
    )}
    per_doc = [{"doc": "a", "report": _agg_report([{"field": "total", "status": "PASS"}], groups=groups)}]
    agg = score.aggregate_reports(per_doc)
    assert agg["group_accuracy"]["charges"]["accuracy"] == 0.75
    assert agg["group_field_accuracy"]["charges"]["amt"]["accuracy"] == 0.5
    assert agg["group_field_accuracy"]["charges"]["desc"]["accuracy"] == 1.0
    assert agg["docs_with_structural_failure"] == 1
    assert agg["group_record_coverage"]["charges"]["not_found"] == 1
    assert agg["group_record_coverage"]["charges"]["matched"] == 1
    assert agg["group_top_misses"][0]["field"] == "charges.amt"


def test_agg_by_dimension_rollup():
    per_doc = [
        {"doc": "e1", "report": _agg_report([{"field": "f", "status": "PASS"}])},
        {"doc": "e2", "report": _agg_report([{"field": "f", "status": "FAIL"}])},
        {"doc": "g1", "report": _agg_report([{"field": "f", "status": "PASS"}])},
    ]
    dims = {"e1": {"service": "electric"}, "e2": {"service": "electric"}, "g1": {"service": "gas"}}
    agg = score.aggregate_reports(per_doc, dims)
    assert agg["by_dimension"]["service"]["electric"] == 0.5
    assert agg["by_dimension"]["service"]["gas"] == 1.0


def test_agg_empty_is_safe():
    agg = score.aggregate_reports([])
    assert agg["documents"] == 0
    assert agg["overall_accuracy"] == 0.0
