#!/usr/bin/env python3
"""Tests for the field-coverage gate (extraction-runner-e2e C6).

These encode the one-directional coverage rule from
references/13_customer_intake.md §5: the authored YAML's field set must cover
the customer's catalog (YAML fields >= catalog fields). Extra YAML fields are
allowed; a missing catalog field is a FAIL.

Run (needs PyYAML + pytest; offline, no API calls):
    python -m pytest templates/test_check_field_coverage.py -q
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_field_coverage import (  # noqa: E402
    catalog_field_names,
    missing_fields,
    yaml_field_names,
)

import yaml  # noqa: E402

_YAML = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
    - name: charge_lines
      level: chunk
      kind: keys
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
        - group: charges
          chain: [reconcile_charges, save_charges]
statement:
  workflow_step: statement_fields
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: a
        type: str
        identifiers: ["Account"]
        instructions: extract account
    total_due:
      workflow_output_key: total_due
      prompt:
        description: a
        type: float
        identifiers: ["Total"]
        instructions: extract total
charges:
  workflow_step: charge_lines
  unique_attrs: [charge_amount]
  match_attrs: [account_number]
  fields:
    charge_description_as_printed:
      workflow_output_key: charge_description_as_printed
      prompt:
        description: a
        type: str
        identifiers: ["Charge"]
        instructions: extract charge
    charge_amount:
      workflow_output_key: charge_amount
      prompt:
        description: a
        type: float
        identifiers: ["Amount"]
        instructions: extract amount
  prompt:
    instructions: "extract records"
"""

_PSEUDO_YAML = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
    - name: customer_packet_step
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
        - group: customer_packet
          chain: [reconcile_statement, qa_statement, save_statement]
_defs:
  common_money:
    fields:
      total_due:
        workflow_output_key: total_due
        prompt:
          description: total
          type: float
          identifiers: ["Total"]
          instructions: extract total
statement:
  include: common_money
  workflow_step: statement_fields
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: a
        type: str
        identifiers: ["Account"]
        instructions: extract account
customer:
  fields:
    customer_name:
      prompt:
        description: a
        type: str
        identifiers: ["Customer"]
        instructions: extract customer
service_address:
  fields:
    street:
      prompt:
        description: a
        type: str
        identifiers: ["Street"]
        instructions: extract street
_pseudo_groups:
  customer_packet:
    workflow_step: customer_packet_step
    fields:
      service_street:
        path: /service_address/street
      customer_name:
        path: /customer/customer_name
"""

_INCLUDE_YAML = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
_defs:
  identity_fields:
    fields:
      account_number:
        workflow_output_key: account_number
        prompt:
          description: account
          type: str
          identifiers: ["Account"]
          instructions: extract account
statement:
  include: identity_fields
  workflow_step: statement_fields
  fields:
    total_due:
      workflow_output_key: total_due
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
"""


def _write(tmp_path, name, text):
    p = os.path.join(tmp_path, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def test_yaml_field_names_ignores_groups_slots_and_metadata():
    names = yaml_field_names(yaml.safe_load(_YAML))
    assert names == {
        "account_number",
        "total_due",
        "charge_description_as_printed",
        "charge_amount",
    }
    # Reserved/structural/business-logic keys must NOT be treated as fields.
    for noise in ("workflow", "statement", "charges", "workflow_step", "fields",
                  "prompt", "unique_attrs", "match_attrs"):
        assert noise not in names


def test_yaml_field_names_uses_final_groups_not_pseudo_aliases():
    names = yaml_field_names(yaml.safe_load(_PSEUDO_YAML))
    assert names == {"account_number", "total_due", "customer_name", "street"}
    assert "service_street" not in names
    assert "common_money" not in names


def test_yaml_field_names_expands_group_level_defs_include():
    names = yaml_field_names(yaml.safe_load(_INCLUDE_YAML))
    assert names == {"account_number", "total_due"}


def test_full_coverage_passes_with_extra_yaml_fields_allowed():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(tmp, "prompt.yaml", _YAML)
        # Catalog is a subset of the YAML fields -> covered.
        cp = _write(tmp, "catalog.json",
                    '["account_number", "charge_amount"]')
        assert missing_fields(yp, cp) == []


def test_missing_catalog_field_is_reported_in_order():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(tmp, "prompt.yaml", _YAML)
        cp = _write(
            tmp, "catalog.json",
            '["account_number", "invoice_date", "tax_id"]',
        )
        # The two fields absent from the YAML, in catalog order.
        assert missing_fields(yp, cp) == ["invoice_date", "tax_id"]


def test_csv_catalog_with_header_and_object_json():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(tmp, "prompt.yaml", _YAML)
        csv_cat = _write(tmp, "catalog.csv",
                         "field\naccount_number\nmissing_one\n")
        assert missing_fields(yp, csv_cat) == ["missing_one"]
        # Object-style JSON catalog resolves the field/name/field_name key.
        obj_cat = _write(
            tmp, "catalog2.json",
            '[{"field": "total_due"}, {"name": "nope"}]',
        )
        assert missing_fields(yp, obj_cat) == ["nope"]
        assert catalog_field_names(obj_cat) == ["total_due", "nope"]


def test_missing_fields_rejects_invalid_v1_source_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(
            tmp,
            "prompt.yaml",
            """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
statement:
  workflow_step: statement_fields
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
""",
        )
        cp = _write(tmp, "catalog.json", '["account_number"]')

        with pytest.raises(ValueError, match="workflow.agent_chain"):
            missing_fields(yp, cp)


def test_missing_fields_rejects_unrouted_v1_source_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(
            tmp,
            "prompt.yaml",
            """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  fields:
    account_number:
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
""",
        )
        cp = _write(tmp, "catalog.json", '["account_number"]')

        with pytest.raises(ValueError, match="not routed|workflow_step|workflow_output_key"):
            missing_fields(yp, cp)


def test_missing_fields_rejects_direct_field_without_output_key():
    with tempfile.TemporaryDirectory() as tmp:
        yp = _write(
            tmp,
            "prompt.yaml",
            """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_fields
  fields:
    account_number:
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
""",
        )
        cp = _write(tmp, "catalog.json", '["account_number"]')

        with pytest.raises(ValueError, match="workflow_output_key"):
            missing_fields(yp, cp)
