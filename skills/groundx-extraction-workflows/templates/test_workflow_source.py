from pathlib import Path
import sys
import types


TEMPLATES = Path(__file__).resolve().parent
if str(TEMPLATES) not in sys.path:
    sys.path.insert(0, str(TEMPLATES))

from _workflow_source import (  # noqa: E402
    load_workflow_source,
    source_yaml_field_names,
)
import batch_extraction  # noqa: E402
import prompt_manager  # noqa: E402
import run_extraction  # noqa: E402


SOURCE = """
extraction_policy_version: v1
_defs:
  common:
    fields:
      account_number:
        type: string
groups:
  ignored_container:
    fields:
      should_not_escape:
        type: string
header:
  include: [common]
  role: statement
  unique_attrs: [account_number]
  discriminator_attrs: [service_type]
  fields:
    service_type:
      type: string
fees:
  role: charges
  match_attrs: [account_number]
  conflict_attrs: [amount]
  passthrough:
    from: header
    fields: [service_type]
  fields:
    amount:
      type: number
_pseudo_groups:
  charge_part:
    role: charges
    fields:
      internal_only:
        type: string
workflow:
  section_strategy: page
  custom_steps:
    - name: extract_statement
      level: section
      kind: instruct
"""


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "prompt.yaml"
    path.write_text(SOURCE, encoding="utf-8")
    return path


def test_load_workflow_source_returns_authored_mapping_without_compilation(tmp_path):
    source = load_workflow_source(_write(tmp_path))

    assert source["workflow"]["custom_steps"][0] == {
        "name": "extract_statement",
        "level": "section",
        "kind": "instruct",
    }
    assert "customSteps" not in source
    assert "outputRoutes" not in source
    assert "leafFields" not in source
    assert "schemaHash" not in source


def test_source_field_names_expand_final_group_includes_only(tmp_path):
    source = load_workflow_source(_write(tmp_path))

    assert source_yaml_field_names(source) == {
        "account_number",
        "service_type",
        "amount",
    }


class _Workflows:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id="created"))

    def update(self, id, **kwargs):
        self.calls.append(("update", id, kwargs))
        return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id=id))


def test_run_batch_and_manager_submit_source_yaml_unchanged(tmp_path):
    yaml_path = tmp_path / "statement.yaml"
    yaml_path.write_text("statement: {}\n", encoding="utf-8")

    run_gx = types.SimpleNamespace(workflows=_Workflows())
    run_extraction._create_workflow(run_gx, yaml_path.read_text(encoding="utf-8"), "test")

    batch_gx = types.SimpleNamespace(workflows=_Workflows())
    batch_extraction._create_workflow(batch_gx, str(yaml_path), "test")

    manager_gx = types.SimpleNamespace(workflows=_Workflows())
    manager = prompt_manager.ExtractionWorkflowManager(manager_gx)
    assert manager.init_prompts(yaml_path=str(yaml_path)) == "created"
    assert manager.update_prompts(workflow_id="wf-1", yaml_path=str(yaml_path)) == "wf-1"

    create_calls = [
        run_gx.workflows.calls[0][1],
        batch_gx.workflows.calls[0][1],
        manager_gx.workflows.calls[0][1],
    ]
    for call in create_calls:
        assert call == {"name": call["name"], "yaml": "statement: {}\n"}
    assert manager_gx.workflows.calls[1][2] == {
        "name": "statement",
        "yaml": "statement: {}\n",
    }
