#!/usr/bin/env python3
"""Tests for client-side post-extraction business logic (extraction-runner-e2e C5).

These encode WHY each primitive matters, not just shapes:
  - dedup must collapse duplicates AND merge non-null fields from the dropped
    duplicate (a later record can fill a field the first left empty).
  - link must resolve a cross-group foreign key (charges -> meters on
    meter_number) so a child knows its parent record.
  - surface_conflicts must expose disagreement as `<field>__conflicts` rather
    than silently picking one value (the whole point is not hiding the clash).
  - apply_passthrough must copy parent fields onto matched children.
  - apply_business_logic with {} must be a strict no-op (backward compatibility:
    a YAML with no business-logic metadata changes nothing).

Run (offline, stdlib-only, no API calls):
    python -m pytest templates/test_business_logic.py -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from business_logic import (  # noqa: E402
    apply_business_logic,
    apply_passthrough,
    dedup,
    link,
    surface_conflicts,
)


def test_dedup_collapses_and_merges_non_null_fields():
    records = [
        {"meter_number": "M-1", "rate": "0.10", "tier": None},
        {"meter_number": "M-1", "rate": None, "tier": "peak"},  # duplicate, fills tier
        {"meter_number": "M-2", "rate": "0.20", "tier": "off"},
    ]
    out = dedup(records, ["meter_number"])
    assert len(out) == 2, "duplicate meter_number should collapse to one record"
    m1 = next(r for r in out if r["meter_number"] == "M-1")
    assert m1["rate"] == "0.10", "kept record's non-null field is preserved"
    assert m1["tier"] == "peak", "non-null field from dropped duplicate is merged in"


def test_dedup_normalizes_case_and_whitespace():
    records = [
        {"id": "abc"},
        {"id": " ABC "},  # same after strip + casefold
    ]
    assert len(dedup(records, ["id"])) == 1


def test_link_resolves_cross_group_foreign_key():
    charges = [{"meter_number": "M-1", "amount": "5"}, {"meter_number": "M-9", "amount": "7"}]
    meters = [{"meter_number": "M-1", "address": "1 Main St"}]
    linked = link(charges, meters, ["meter_number"])
    matched = next(c for c in linked if c["meter_number"] == "M-1")
    assert matched["_parent"] == {"meter_number": "M-1", "address": "1 Main St"}
    unmatched = next(c for c in linked if c["meter_number"] == "M-9")
    assert unmatched["_parent"] is None, "no matching parent -> _parent is None"


def test_surface_conflicts_exposes_disagreement():
    records = [
        {"meter_number": "M-1", "address": "1 Main St"},
        {"meter_number": "M-1", "address": "1 Main Street"},  # disagrees
    ]
    out = surface_conflicts(records, ["address"])
    assert all("address__conflicts" in r for r in out), "every record carries the conflict"
    assert out[0]["address__conflicts"] == ["1 Main St", "1 Main Street"]


def test_surface_conflicts_noop_when_agreeing():
    records = [{"address": "1 Main St"}, {"address": "1 Main St"}]
    out = surface_conflicts(records, ["address"])
    assert not any("address__conflicts" in r for r in out)


def test_apply_passthrough_copies_parent_fields_onto_children():
    charges = [{"meter_number": "M-1", "amount": "5"}]
    meters = [{"meter_number": "M-1", "address": "1 Main St", "site": "A"}]
    out = apply_passthrough(charges, meters, ["meter_number"], ["address", "site"])
    assert out[0]["address"] == "1 Main St"
    assert out[0]["site"] == "A"
    assert "_parent" not in out[0], "passthrough should not leak the _parent annotation"


def test_apply_business_logic_empty_metadata_is_noop():
    doc = {
        "account_id": "X",
        "account_charges": [{"meter_number": "M-1"}, {"meter_number": "M-1"}],
        "meters": [{"meter_number": "M-1", "address": "1 Main St"}],
    }
    assert apply_business_logic(doc, {}) == doc
    assert apply_business_logic(dict(doc), None) == doc


def test_apply_business_logic_orchestrates_dedup_passthrough_conflicts():
    doc = {
        "account_charges": [
            {"meter_number": "M-1", "amount": "5"},
            {"meter_number": "M-1", "amount": "5"},  # exact dup -> collapses
        ],
        "meters": [
            {"meter_number": "M-1", "address": "1 Main St"},
            {"meter_number": "M-1", "address": "1 Main Street"},  # conflict on address
        ],
    }
    metadata = {
        "meters": {
            "unique_attrs": ["meter_number"],
            "conflict_attrs": ["address"],
        },
        "account_charges": {
            "unique_attrs": ["meter_number", "amount"],
            "match_attrs": ["meter_number"],
            "passthrough": {"from": "meters", "fields": ["address"]},
        },
    }
    out = apply_business_logic(doc, metadata)

    # meters deduped to one record (kept first), with the address conflict surfaced.
    assert len(out["meters"]) == 1
    assert out["meters"][0]["address__conflicts"] == ["1 Main St", "1 Main Street"]

    # charges deduped to one, with parent address passed through.
    assert len(out["account_charges"]) == 1
    assert out["account_charges"][0]["address"] == "1 Main St"

    # input not mutated.
    assert len(doc["account_charges"]) == 2


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))


def test_dedup_reaches_renamed_account_charges_group():
    """Warner-found gap: YAML declares group `charges`, but aggregated records
    live under `account_charges` (xray_to_extract rename). dedup must still
    reach them via the group-alias resolver."""
    doc = {"account_charges": [
        {"charge_description_as_printed": "State Tax", "charge_amount": "5.00"},
        {"charge_description_as_printed": "State Tax", "charge_amount": "5.00"},
    ]}
    out = apply_business_logic(
        doc, {"charges": {"unique_attrs": ["charge_description_as_printed", "charge_amount"]}}
    )
    assert len(out["account_charges"]) == 1, "dedup must reach the renamed account_charges group"
