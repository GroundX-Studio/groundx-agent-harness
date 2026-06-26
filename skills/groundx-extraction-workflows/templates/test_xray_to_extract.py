"""Tests for local X-Ray aggregation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xray_to_extract import xray_to_extract  # noqa: E402


def test_xray_to_extract_maps_custom_outputs_to_final_paths():
    workflow_extract = {
        "workflow": {
            "output_routes": [
                {
                    "workflow_group": "line_items",
                    "workflow_field": "description",
                    "final_path": "/line_items/*/description",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "label",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/label",
                },
                {
                    "workflow_group": "summary",
                    "workflow_field": "invoice_type",
                    "final_path": "/summary/invoice_type",
                    "step_name": "invoice_summary",
                    "level": "document",
                    "output_map": "customDocumentOutputs",
                    "output_key": "invoice_type",
                    "readback_path": (
                        "/customDocumentOutputs/invoice_summary/invoice_type"
                    ),
                },
            ]
        }
    }
    xray = {
        "customDocumentOutputs": {
            "invoice_summary": {"invoice_type": "utility"}
        },
        "chunks": [
            {
                "customChunkOutputs": {
                    "line_item_labels": {"label": "Generation charge"}
                }
            },
            {
                "customChunkOutputs": {
                    "line_item_labels": {"label": "Distribution charge"}
                }
            },
        ],
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract) == {
        "summary": {"invoice_type": "utility"},
        "line_items": [
            {"description": "Generation charge"},
            {"description": "Distribution charge"},
        ],
    }


def test_xray_to_extract_custom_routes_ignore_legacy_fallback_noise():
    workflow_extract = {
        "workflow": {
            "output_routes": [
                {
                    "workflow_group": "plan_summary",
                    "workflow_field": "plan_name",
                    "final_path": "/plan_information/plan_name",
                    "step_name": "plan_summary_step",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "plan_name",
                },
            ]
        }
    }
    xray = {
        "chunks": [
            {
                "sectionSummary": '{"account_number": "legacy-account"}',
                "chunkKeywords": '{"charges": [{"description": "legacy charge"}]}',
                "chunkSummary": '{"meters": [{"meter_number": "legacy-meter"}]}',
                "suggestedText": '{"meters": [{"meter_number": "legacy-meter-2"}]}',
                "customChunkOutputs": {
                    "plan_summary_step": {"plan_name": "retirement plan"}
                },
            }
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract) == {
        "plan_information": {"plan_name": "retirement plan"}
    }


def test_xray_to_extract_preserves_nested_repeated_custom_paths():
    workflow_extract = {
        "workflow": {
            "output_routes": [
                {
                    "workflow_group": "charges",
                    "workflow_field": "description",
                    "final_path": "/invoice/charges/*/description",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "label",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/label",
                },
            ]
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "line_item_labels": {"label": "Transmission charge"}
                }
            },
        ],
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["invoice"] == {
        "charges": [{"description": "Transmission charge"}]
    }


def test_xray_to_extract_groups_repeated_custom_fields_from_same_chunk():
    workflow_extract = {
        "workflow": {
            "output_routes": [
                {
                    "workflow_group": "line_items",
                    "workflow_field": "description",
                    "final_path": "/line_items/*/description",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "description",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/description",
                },
                {
                    "workflow_group": "line_items",
                    "workflow_field": "amount",
                    "final_path": "/line_items/*/amount",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "amount",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/amount",
                },
            ]
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "line_item_labels": {
                        "description": "Generation charge",
                        "amount": "$10.00",
                    }
                }
            },
            {
                "customChunkOutputs": {
                    "line_item_labels": {
                        "description": "Distribution charge",
                        "amount": "$4.00",
                    }
                }
            },
        ],
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["line_items"] == [
        {"description": "Generation charge", "amount": "$10.00"},
        {"description": "Distribution charge", "amount": "$4.00"},
    ]


def test_xray_to_extract_expands_repeated_custom_field_arrays_from_one_chunk():
    workflow_extract = {
        "workflow": {
            "custom_steps": [
                {"name": "charge_lines", "level": "chunk", "kind": "keys"},
            ],
            "output_routes": [
                {
                    "workflow_group": "charges",
                    "workflow_field": "description",
                    "final_path": "/charges/*/description",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "description",
                },
                {
                    "workflow_group": "charges",
                    "workflow_field": "amount",
                    "final_path": "/charges/*/amount",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "amount",
                },
            ],
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "charge_lines": {
                        "description": ["Generation charge", "Distribution charge"],
                        "amount": ["10.00", "4.00"],
                    }
                }
            }
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["charges"] == [
        {"description": "Generation charge", "amount": "10.00"},
        {"description": "Distribution charge", "amount": "4.00"},
    ]


def test_xray_to_extract_expands_repeated_custom_record_lists_from_one_chunk():
    workflow_extract = {
        "workflow": {
            "custom_steps": [
                {"name": "charge_lines", "level": "chunk", "kind": "keys"},
            ],
            "output_routes": [
                {
                    "workflow_group": "charges",
                    "workflow_field": "description",
                    "final_path": "/charges/*/description",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "description",
                },
                {
                    "workflow_group": "charges",
                    "workflow_field": "amount",
                    "final_path": "/charges/*/amount",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "amount",
                },
            ],
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "charge_lines": [
                        {"description": "Generation charge", "amount": "10.00"},
                        {"description": "Distribution charge", "amount": "4.00"},
                    ]
                }
            }
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["charges"] == [
        {"description": "Generation charge", "amount": "10.00"},
        {"description": "Distribution charge", "amount": "4.00"},
    ]


def test_xray_to_extract_dedupes_repeated_custom_fields_from_mirrored_chunks():
    workflow_extract = {
        "workflow": {
            "output_routes": [
                {
                    "workflow_group": "line_items",
                    "workflow_field": "description",
                    "final_path": "/line_items/*/description",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "description",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/description",
                },
                {
                    "workflow_group": "line_items",
                    "workflow_field": "amount",
                    "final_path": "/line_items/*/amount",
                    "step_name": "line_item_labels",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "amount",
                    "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/amount",
                },
            ]
        }
    }
    chunk = {
        "customChunkOutputs": {
            "line_item_labels": {
                "description": "Generation charge",
                "amount": "$10.00",
            }
        }
    }
    xray = {
        "chunks": [chunk],
        "documentPages": [
            {
                "chunks": [
                    {
                        "customChunkOutputs": {
                            "line_item_labels": {
                                "description": "Generation charge",
                                "amount": "$10.00",
                            }
                        }
                    }
                ]
            }
        ],
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["line_items"] == [
        {"description": "Generation charge", "amount": "$10.00"},
    ]


def test_xray_to_extract_preserves_compiled_summary_routes():
    workflow_extract = {
        "workflow": {
            "custom_steps": [
                {"name": "meter_lines", "level": "chunk", "kind": "summary"},
            ],
            "output_routes": [
                {
                    "workflow_group": "meters",
                    "workflow_field": "meter_number",
                    "final_path": "/meters/meter_number",
                    "step_name": "meter_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "meter_number",
                },
            ],
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "meter_lines": {"meter_number": "M1"},
                }
            }
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["meters"] == [
        {"meter_number": "M1"}
    ]


def test_xray_to_extract_preserves_compiled_keys_routes_with_multiple_fields():
    workflow_extract = {
        "workflow": {
            "custom_steps": [
                {"name": "charge_lines", "level": "chunk", "kind": "keys"},
            ],
            "output_routes": [
                {
                    "workflow_group": "charges",
                    "workflow_field": "charge_description_as_printed",
                    "final_path": "/charges/charge_description_as_printed",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "charge_description_as_printed",
                },
                {
                    "workflow_group": "charges",
                    "workflow_field": "charge_amount",
                    "final_path": "/charges/charge_amount",
                    "step_name": "charge_lines",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "charge_amount",
                },
            ],
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "charge_lines": {
                        "charge_description_as_printed": "Generation charge",
                        "charge_amount": "10.00",
                    },
                }
            },
            {
                "customChunkOutputs": {
                    "charge_lines": {
                        "charge_description_as_printed": "Distribution charge",
                        "charge_amount": "4.00",
                    },
                }
            },
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["charges"] == [
        {"charge_description_as_printed": "Generation charge", "charge_amount": "10.00"},
        {"charge_description_as_printed": "Distribution charge", "charge_amount": "4.00"},
    ]


def test_xray_to_extract_does_not_overwrite_custom_group_with_empty_fallback():
    workflow_extract = {
        "workflow": {
            "custom_steps": [
                {"name": "meter_status", "level": "chunk", "kind": "instruct"},
            ],
            "output_routes": [
                {
                    "workflow_group": "meters",
                    "workflow_field": "status",
                    "final_path": "/meters/status",
                    "step_name": "meter_status",
                    "level": "chunk",
                    "output_map": "customChunkOutputs",
                    "output_key": "status",
                },
            ],
        }
    }
    xray = {
        "chunks": [
            {
                "customChunkOutputs": {
                    "meter_status": {"status": "active"},
                }
            }
        ]
    }

    assert xray_to_extract(xray, workflow_extract=workflow_extract)["meters"] == {
        "status": "active"
    }
