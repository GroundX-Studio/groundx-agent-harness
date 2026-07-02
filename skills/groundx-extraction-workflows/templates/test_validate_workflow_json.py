"""Contract tests for custom workflow-step structural validation."""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_workflow_json import REQUIRED_SLOTS, validate  # noqa: E402


def _steps() -> dict:
    return {slot: None for slot in REQUIRED_SLOTS}


def _custom_workflow() -> dict:
    return {
        "name": "custom workflow",
        "extract": {
            "line_items": {"fields": {}},
            "workflow": {
                "metadata_version": 1,
                "template": {"BILLING_HINT": "Prefer charge table values."},
                "custom_steps": [
                    {
                        "name": "line_item_labels",
                        "level": "chunk",
                        "kind": "keys",
                    }
                ],
                "output_routes": [
                    {
                        "workflow_group": "line_items",
                        "workflow_field": "description",
                        "final_path": "/line_items/*/description",
                        "step_name": "line_item_labels",
                        "level": "chunk",
                        "output_map": "customChunkOutputs",
                        "output_key": "label",
                        "readback_path": (
                            "/chunks/*/customChunkOutputs/line_item_labels/label"
                        ),
                    }
                ],
                "leaf_fields": [
                    {
                        "final_path": "/line_items/*/description",
                        "workflow_group": "line_items",
                        "workflow_field": "description",
                        "step_name": "line_item_labels",
                        "level": "chunk",
                        "output_key": "label",
                        "field_type": "str",
                        "is_repeated": True,
                        "repetition_scope": "item",
                    }
                ],
            },
        },
        "steps": _steps(),
        "template": {"BILLING_HINT": "Prefer charge table values."},
        "customSteps": [
            {
                "name": "line_item_labels",
                "level": "chunk",
                "kind": "keys",
                "requiredTemplateKeys": ["BILLING_HINT"],
                "config": {
                    "all": {
                        "includes": {"pageImages": True},
                        "prompt": {
                            "request": "Extract label.",
                            "task": "Return label.",
                        },
                    }
                },
            }
        ],
        "outputRoutes": [
            {
                "workflowGroup": "line_items",
                "workflowField": "description",
                "finalPath": "/line_items/*/description",
                "stepName": "line_item_labels",
                "level": "chunk",
                "outputMap": "customChunkOutputs",
                "outputKey": "label",
                "readbackPath": "/chunks/*/customChunkOutputs/line_item_labels/label",
            }
        ],
        "leafFields": [
            {
                "finalPath": "/line_items/*/description",
                "workflowGroup": "line_items",
                "workflowField": "description",
                "stepName": "line_item_labels",
                "level": "chunk",
                "outputKey": "label",
                "fieldType": "str",
                "isRepeated": True,
                "repetitionScope": "item",
            }
        ],
    }


def test_validate_accepts_custom_steps_routes_and_leaf_fields():
    assert validate(_custom_workflow()) == []


def test_validate_rejects_custom_workflow_without_persisted_workflow_metadata():
    workflow = _custom_workflow()
    del workflow["extract"]["workflow"]

    assert any("extract.workflow" in error for error in validate(workflow))


def test_validate_rejects_custom_workflow_without_persisted_custom_steps():
    workflow = _custom_workflow()
    del workflow["extract"]["workflow"]["custom_steps"]

    assert any("extract.workflow.custom_steps" in error for error in validate(workflow))


def test_validate_rejects_custom_workflow_without_persisted_output_routes():
    workflow = _custom_workflow()
    del workflow["extract"]["workflow"]["output_routes"]

    assert any("extract.workflow.output_routes" in error for error in validate(workflow))


def test_validate_rejects_custom_workflow_without_persisted_leaf_fields():
    workflow = _custom_workflow()
    del workflow["extract"]["workflow"]["leaf_fields"]

    assert any("extract.workflow.leaf_fields" in error for error in validate(workflow))


def test_validate_rejects_persisted_output_route_contract_drift():
    workflow = _custom_workflow()
    workflow["extract"]["workflow"]["output_routes"][0]["readback_path"] = (
        "/chunks/*/customChunkOutputs/line_item_labels/wrong"
    )

    assert any("extract.workflow.output_routes" in error for error in validate(workflow))


def test_validate_rejects_persisted_leaf_field_contract_drift():
    workflow = _custom_workflow()
    workflow["extract"]["workflow"]["leaf_fields"][0]["repetition_scope"] = "none"

    assert any("extract.workflow.leaf_fields" in error for error in validate(workflow))


def test_validate_rejects_missing_persisted_leaf_field_contract_field():
    workflow = _custom_workflow()
    del workflow["extract"]["workflow"]["leaf_fields"][0]["is_repeated"]

    assert any("extract.workflow.leaf_fields" in error for error in validate(workflow))


def test_validate_accepts_pseudo_group_routes_to_final_fields():
    workflow = _custom_workflow()
    workflow["extract"] = {
        "statement_identity": {
            "fields": {
                "account_number": {
                    "prompt": {
                        "description": "account",
                        "type": "str",
                        "identifiers": ["Account"],
                        "instructions": "extract account",
                    }
                }
            }
        },
        "_groundx_persisted_extract": {
            "extraction_policy_version": "v1",
            "workflow": {
                "custom_steps": [
                    {
                        "name": "statement_labels",
                        "level": "chunk",
                        "kind": "instruct",
                    }
                ]
            },
            "statement": {
                "fields": {
                    "account_number": {
                        "prompt": {
                            "description": "account",
                            "type": "str",
                            "identifiers": ["Account"],
                            "instructions": "extract account",
                        }
                    }
                }
            },
            "_pseudo_groups": {
                "statement_identity": {
                    "workflow_step": "statement_labels",
                    "fields": {
                        "account_number": {"path": "/statement/account_number"}
                    },
                }
            },
        },
    }
    workflow["customSteps"] = [
        {
            "name": "statement_labels",
            "level": "chunk",
            "kind": "instruct",
            "config": {
                "all": {
                    "includes": {"pageImages": True},
                    "prompt": {
                        "request": "Extract account.",
                        "task": "Return account.",
                    },
                }
            },
        }
    ]
    workflow["outputRoutes"] = [
        {
            "workflowGroup": "statement_identity",
            "workflowField": "account_number",
            "finalPath": "/statement/account_number",
            "stepName": "statement_labels",
            "level": "chunk",
            "outputMap": "customChunkOutputs",
            "outputKey": "account_number",
            "readbackPath": (
                "/chunks/*/customChunkOutputs/statement_labels/account_number"
            ),
        }
    ]
    workflow["leafFields"] = [
        {
            "finalPath": "/statement/account_number",
            "workflowGroup": "statement_identity",
            "workflowField": "account_number",
            "stepName": "statement_labels",
            "level": "chunk",
            "outputKey": "account_number",
            "fieldType": "str",
            "isRepeated": False,
            "repetitionScope": "none",
        }
    ]
    workflow["extract"]["workflow"] = {
        "metadata_version": 1,
        "custom_steps": [
            {
                "name": "statement_labels",
                "level": "chunk",
                "kind": "instruct",
            }
        ],
        "output_routes": [
            {
                "workflow_group": "statement_identity",
                "workflow_field": "account_number",
                "final_path": "/statement/account_number",
                "step_name": "statement_labels",
                "level": "chunk",
                "output_map": "customChunkOutputs",
                "output_key": "account_number",
                "readback_path": (
                    "/chunks/*/customChunkOutputs/statement_labels/account_number"
                ),
            }
        ],
        "leaf_fields": [
            {
                "final_path": "/statement/account_number",
                "workflow_group": "statement_identity",
                "workflow_field": "account_number",
                "step_name": "statement_labels",
                "level": "chunk",
                "output_key": "account_number",
                "field_type": "str",
                "is_repeated": False,
                "repetition_scope": "none",
            }
        ],
    }

    assert validate(workflow) == []


def test_validate_rejects_route_leaf_mismatch():
    workflow = _custom_workflow()
    workflow["leafFields"][0]["finalPath"] = "/line_items/*/amount"

    assert any("route" in error and "leaf" in error for error in validate(workflow))


def test_validate_rejects_extract_group_without_custom_route():
    workflow = _custom_workflow()
    workflow["extract"]["charges"] = {
        "fields": {
            "amount": {
                "prompt": {
                    "description": "amount",
                    "type": "float",
                    "identifiers": ["Amount"],
                    "instructions": "extract amount",
                }
            }
        }
    }

    assert any("extract group 'charges'" in error for error in validate(workflow))


def test_validate_rejects_unused_custom_step():
    workflow = _custom_workflow()
    workflow["customSteps"].append(
        {
            "name": "unused_step",
            "level": "chunk",
            "kind": "instruct",
            "config": {
                "all": {
                    "includes": {"pageImages": True},
                    "prompt": {
                        "request": "Extract unused.",
                        "task": "Return unused.",
                    },
                }
            },
        }
    )

    assert any("custom step 'unused_step' has no output routes" in error for error in validate(workflow))


def test_validate_rejects_custom_step_without_all_prompt():
    workflow = _custom_workflow()
    del workflow["customSteps"][0]["config"]["all"]["prompt"]

    assert any(
        "custom step 'line_item_labels' must define config.all.prompt.request and task"
        in error
        for error in validate(workflow)
    )


def test_validate_rejects_custom_step_over_30_fields():
    workflow = _custom_workflow()
    route = workflow["outputRoutes"][0]
    leaf = workflow["leafFields"][0]
    workflow["outputRoutes"] = []
    workflow["leafFields"] = []
    for idx in range(31):
        next_route = copy.deepcopy(route)
        next_leaf = copy.deepcopy(leaf)
        next_route["workflowField"] = f"field_{idx}"
        next_route["finalPath"] = f"/line_items/*/field_{idx}"
        next_route["outputKey"] = f"label_{idx}"
        next_route["readbackPath"] = (
            f"/chunks/*/customChunkOutputs/line_item_labels/label_{idx}"
        )
        next_leaf["workflowField"] = f"field_{idx}"
        next_leaf["finalPath"] = f"/line_items/*/field_{idx}"
        next_leaf["outputKey"] = f"label_{idx}"
        workflow["outputRoutes"].append(next_route)
        workflow["leafFields"].append(next_leaf)

    assert any("at most 30" in error for error in validate(workflow))


def test_validate_rejects_invalid_custom_step_kind():
    workflow = _custom_workflow()
    workflow["customSteps"][0]["kind"] = "records"

    assert any("invalid custom step kind" in error for error in validate(workflow))


def test_validate_rejects_document_instruct_step():
    workflow = _custom_workflow()
    workflow["customSteps"][0]["level"] = "document"
    workflow["customSteps"][0]["kind"] = "instruct"
    workflow["outputRoutes"][0]["level"] = "document"
    workflow["outputRoutes"][0]["outputMap"] = "customDocumentOutputs"
    workflow["outputRoutes"][0]["readbackPath"] = (
        "/customDocumentOutputs/line_item_labels/label"
    )
    workflow["leafFields"][0]["level"] = "document"

    assert any("invalid custom step level/kind" in error for error in validate(workflow))


def test_validate_rejects_invalid_repeated_item_wildcard():
    workflow = _custom_workflow()
    workflow["leafFields"][0]["finalPath"] = "/line_items/description"
    workflow["leafFields"][0]["repetitionScope"] = "/line_items"

    assert any("wildcard" in error for error in validate(workflow))


def test_validate_rejects_path_format_repetition_scope():
    """Repeated leaves must use the 'item' enum, not the legacy /path/* format.

    The live GroundX API only accepts none/field/item and rejects path-format
    values ('unsupported repetitionScope /meters/*'). Guards AGE-150.
    """
    workflow = _custom_workflow()
    workflow["leafFields"][0]["repetitionScope"] = "/line_items/*"

    assert any("repetitionScope" in error for error in validate(workflow))


def test_validate_rejects_repeated_custom_step_without_repeated_route_metadata():
    workflow = _custom_workflow()
    workflow["outputRoutes"][0]["finalPath"] = "/line_items/description"
    workflow["leafFields"][0]["finalPath"] = "/line_items/description"
    workflow["leafFields"][0]["isRepeated"] = False
    workflow["leafFields"][0]["repetitionScope"] = "none"

    errors = validate(workflow)

    assert any("repeated custom step" in error for error in errors)
