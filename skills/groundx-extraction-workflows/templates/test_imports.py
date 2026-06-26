"""Import-smoke test: every shipped template module must import cleanly.

Run: python -m pytest templates/test_imports.py -q

`py_compile` (the node gate) only checks syntax — it does NOT catch a module
that imports a name a sibling no longer exports (e.g. after a refactor renames
or removes a function). This test imports each module so that class of breakage
fails loudly. Modules that need the GroundX SDK are skipped only when the SDK
is absent; any *other* ImportError is a real failure.
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    "compile_workflow",
    "validate_workflow_json",
    "xray_to_extract",
    "business_logic",
    "run_log",
    "check_field_coverage",
    "score_extraction",
    "batch_score",
    "deploy_workflow",
    "run_extraction",
    "batch_extraction",
    "prompt_manager",
    "cleanup_orphans",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    try:
        importlib.import_module(module)
    except ImportError as e:
        if "groundx" in str(e).lower():
            pytest.skip("GroundX SDK not installed in this environment")
        raise
