#!/usr/bin/env python3
"""Contract tests for the workflow_step compiler.

Test-first: these encode the harness compile contract from the OpenSpec change
`extraction-runner-e2e`. Harness-authored YAML uses `workflow.custom_steps` plus
per-workflow-group `workflow_step:` metadata. Legacy `slot:` and `domain:` YAMLs
belong to runtime compatibility and SDK compatibility helpers, not the Studio
Harness templates.

Run (needs the groundx SDK + pytest installed; offline, no API calls):
    python -m pytest templates/test_compile_workflow.py -q

Lives with the templates so it shares their import path and SDK context.
"""

import copy
import json
import os
import sys
import tempfile
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compile_workflow  # noqa: E402
import batch_extraction  # noqa: E402
import deploy_workflow  # noqa: E402
import prompt_manager  # noqa: E402
import run_extraction  # noqa: E402
from compile_workflow import build_workflow  # noqa: E402

# A minimal valid field block (the SDK requires prompt sub-keys).
_F = (
    "    {name}:\n"
    "      prompt:\n"
    "        description: a field\n"
    "        type: str\n"
    "        identifiers: [\"Label\"]\n"
    "        instructions: extract it\n"
)


def _write(yaml_text: str) -> str:
    d = tempfile.mkdtemp(prefix="c2-")
    path = os.path.join(d, "prompt.yaml")
    with open(path, "w") as f:
        f.write(yaml_text)
    return path


def _slots(workflow: dict) -> list:
    return sorted(k for k, v in (workflow.get("steps") or {}).items() if v)


def _workflow_with_persisted_extract() -> dict:
    return {
        "name": "test",
        "chunk_strategy": "element",
        "section_strategy": "page",
        "extract": {
            "statement": {"fields": {}},
            "_groundx_persisted_extract": {"domain": "invoice"},
        },
        "steps": {"chunk-instruct": None},
        "template": {"BILLING_HINT": "Prefer charge table values."},
        "customSteps": [{"name": "line_item_labels", "level": "chunk", "kind": "keys"}],
        "outputRoutes": [{"stepName": "line_item_labels", "outputKey": "label"}],
        "leafFields": [{"stepName": "line_item_labels", "outputKey": "label"}],
    }


def test_extract_group_counts_are_domain_neutral():
    counts = run_extraction._extract_group_counts(
        {
            "claim": {"claim_number": "C-1", "status": "open"},
            "line_items": [{"amount": "10.00"}, {"amount": "4.00"}],
            "empty_group": [],
            "approved": True,
            "missing": "",
        }
    )

    assert counts == {
        "claim": 2,
        "line_items": 2,
        "empty_group": 0,
        "approved": 1,
        "missing": 0,
    }


def test_format_group_counts_is_domain_neutral():
    assert (
        run_extraction._format_group_counts({"claim": 2, "line_items": 2})
        == "claim=2,line_items=2"
    )
    assert run_extraction._format_group_counts({}) == "none"


def _custom_yaml() -> str:
    return """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""


def _custom_yaml_with_two_statement_fields() -> str:
    return """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  prompt:
    instructions: Extract only statement identity fields.
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account identifier
        type: str
        identifiers: ["Account", "Acct"]
        instructions: extract account exactly as written
    plan_name:
      workflow_output_key: plan_name
      prompt:
        description: plan display name
        type: str
        identifiers: ["Plan Name"]
        instructions: extract plan name exactly as written
"""


def _custom_yaml_with_section_strategy() -> str:
    return _custom_yaml().replace(
        "workflow:\n",
        "workflow:\n  section_strategy: page\n",
        1,
    )


def _oversized_custom_yaml(field_count: int = 31) -> str:
    fields = []
    for index in range(field_count):
        fields.append(
            f"""
    field_{index}:
      workflow_output_key: field_{index}
      prompt:
        description: field {index}
        type: str
        identifiers: ["Field {index}"]
        instructions: extract field {index}
""".rstrip()
        )
    return (
        """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
"""
        + "\n".join(fields)
        + "\n"
    )


def _valid_agent_chain(group: str = "statement") -> str:
    return f"""
  agent_chain:
    - parallel:
        - group: {group}
          chain: [reconcile_statement, qa_statement]
    - save_statement
"""


def _custom_yaml_without_agent_chain() -> str:
    return """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""


def test_domain_yaml_is_not_supported_by_harness_templates():
    """Legacy domain profiles are not a harness authoring path."""
    y = "domain: invoice\nstatement:\n  fields:\n" + _F.format(name="acct_id")

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "do not support retired `domain:`" in message
    assert "workflow_step:" in message
    assert "new harness-authored YAML" in message


def test_slot_yaml_is_not_supported_by_harness_templates():
    """Legacy slot YAML is rejected instead of compiled."""
    y = "claimant:\n  slot: chunk-instruct\n  fields:\n" + _F.format(name="claim_id")

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "uses retired `slot:`" in message
    assert "workflow.custom_steps" in message
    assert "workflow_step:" in message


def test_plain_yaml_without_workflow_step_errors_with_remedy():
    """Harness YAML must declare the custom workflow_step path."""
    y = "statement:\n  fields:\n" + _F.format(name="account_number")

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "extraction_policy_version: v1" in message


def test_custom_workflow_requires_extraction_policy_v1(monkeypatch):
    """Harness source YAML must use the explicit v1 authoring contract."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""

    with pytest.raises(ValueError, match="extraction_policy_version: v1"):
        build_workflow(_write(y))


def test_custom_workflow_requires_agent_chain(monkeypatch):
    """Runtime-owned workflows need an explicit persisted agent task chain."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)

    with pytest.raises(ValueError, match="workflow.agent_chain"):
        build_workflow(_write(_custom_yaml_without_agent_chain()))


def test_source_yaml_rejects_persisted_workflow_payload():
    """Downloaded workflow extract metadata is readback, not source YAML."""
    y = _custom_yaml().replace(
        "statement:\n",
        "_groundx_persisted_extract:\n  statement: {}\nstatement:\n",
        1,
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "_groundx_persisted_extract" in message
    assert "Compile from v1 source YAML" in message


def test_source_yaml_rejects_generated_workflow_readback_key():
    """Workflow JSON fields must not be accepted as authoring YAML."""
    y = _custom_yaml().replace(
        "statement:\n",
        "customSteps:\n  - name: statement_labels\nstatement:\n",
        1,
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "customSteps" in message
    assert "workflow readback" in message


def test_source_validation_runs_before_sdk_prepare(monkeypatch):
    """Invalid source YAML must fail before the optional SDK helper runs."""

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("SDK prepare should not be called for invalid source YAML")

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        fail_if_called,
        raising=False,
    )
    y = _custom_yaml().replace(
        "statement:\n",
        "customSteps:\n  - name: statement_labels\nstatement:\n",
        1,
    )

    with pytest.raises(ValueError, match="workflow readback"):
        build_workflow(_write(y))


def test_generated_workflow_key_can_be_valid_final_group_name(monkeypatch):
    """Arbitrary final group names still work when shaped like source groups."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = _custom_yaml().replace("statement_labels", "name_labels").replace(
        "statement:",
        "name:",
    ).replace(
        "- group: statement",
        "- group: name",
    )

    wf = build_workflow(_write(y))

    assert wf["outputRoutes"][0]["finalPath"] == "/name/account_number"
    assert "name" in wf["extract"]["_groundx_persisted_extract"]


def test_custom_workflow_rejects_unsupported_custom_step_keys():
    """Custom steps are part of the source whitelist."""
    y = _custom_yaml().replace(
        "      kind: instruct\n",
        "      kind: instruct\n      retries: 2\n",
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "workflow.custom_steps[0]" in message
    assert "retries" in message


def test_custom_workflow_requires_full_prompt_object():
    """Field prompts use the explicit v1 prompt shape."""
    y = _custom_yaml().replace(
        '        identifiers: ["Account"]\n        instructions: extract account\n',
        "",
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "statement.account_number.prompt" in message
    assert "identifiers" in message
    assert "instructions" in message


def test_custom_workflow_rejects_non_mapping_field():
    """A bad field shape should fail as source YAML, not as vague route fallout."""
    y = _custom_yaml().replace(
        """    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
""",
        "    account_number: account\n",
    )

    with pytest.raises(ValueError, match="statement.account_number must be a field mapping"):
        build_workflow(_write(y))


def test_custom_workflow_rejects_unsupported_field_keys():
    """Leaf fields are a whitelist, not a bag for arbitrary metadata."""
    y = _custom_yaml().replace(
        "      workflow_output_key: account_number\n",
        "      workflow_output_key: account_number\n      confidence_hint: high\n",
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "statement.account_number" in message
    assert "confidence_hint" in message


def test_custom_workflow_rejects_unsupported_final_group_keys():
    """Final groups may carry known business metadata, not arbitrary keys."""
    y = _custom_yaml().replace(
        "  workflow_step: statement_labels\n",
        "  workflow_step: statement_labels\n  owner_notes: internal\n",
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "final group 'statement'" in message
    assert "owner_notes" in message


def test_custom_workflow_rejects_oversized_workflow_group():
    """Executable workflow groups are capped at 30 prompted fields."""
    with pytest.raises(ValueError) as exc:
        build_workflow(_write(_oversized_custom_yaml()))

    message = str(exc.value)
    assert "workflow group 'statement'" in message
    assert "31 fields" in message
    assert "30 fields or fewer" in message


def test_str_field_rejects_native_json_array_instruction(monkeypatch):
    """A str field may ask for JSON encoded as a string, not a native array."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = _custom_yaml().replace(
        "instructions: extract account",
        "instructions: Return a JSON array of objects, or null when absent.",
    )

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "statement.account_number" in message
    assert "type: str" in message
    assert "JSON-encoded string" in message


def test_custom_workflow_rejects_unrouted_workflow_group():
    """Custom-step YAML must not silently leave a workflow group unrouted."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
charges:
  fields:
    amount:
      prompt:
        description: amount
        type: float
        identifiers: ["Amount"]
        instructions: extract amount
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "final group 'charges'" in message
    assert "workflow_step:" in message


def test_custom_workflow_rejects_routed_field_without_output_key():
    """Routed fields must name their custom output key explicitly."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "statement.account_number" in message
    assert "workflow_output_key" in message


def test_custom_workflow_compiles_authored_pseudo_groups():
    """Pseudo groups split execution while preserving the final output group."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
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
_pseudo_groups:
  statement_identity:
    workflow_step: statement_labels
    prompt:
      instructions: Extract statement identity fields.
    fields:
      account_number:
        path: /statement/account_number
"""

    wf = build_workflow(_write(y))

    assert "statement_identity" in wf["extract"]
    assert "statement" not in wf["extract"]
    assert wf["extract"]["statement_identity"]["prompt"]["instructions"] == (
        "Extract statement identity fields."
    )
    assert wf["extract"]["statement_identity"]["fields"]["account_number"]["prompt"][
        "description"
    ] == "account"
    assert wf["outputRoutes"] == [
        {
            "workflowGroup": "statement_identity",
            "workflowField": "account_number",
            "finalPath": "/statement/account_number",
            "stepName": "statement_labels",
            "level": "chunk",
            "outputMap": "customChunkOutputs",
            "outputKey": "account_number",
            "readbackPath": "/chunks/*/customChunkOutputs/statement_labels/account_number",
        }
    ]
    authored = wf["extract"]["_groundx_persisted_extract"]
    assert "statement" in authored
    assert "_pseudo_groups" in authored
    assert authored["_pseudo_groups"]["statement_identity"]["fields"]["account_number"] == {
        "path": "/statement/account_number"
    }


def _required_prompt_molecules() -> tuple[str, ...]:
    return ("all", "figure", "paragraph", "table-figure")


def _custom_step_by_name(workflow: dict, name: str) -> dict:
    for step in workflow.get("customSteps") or []:
        if step.get("name") == name:
            return step
    raise AssertionError(f"custom step {name!r} not found")


def _prompt_pair(step: dict, molecule: str) -> tuple[str, str]:
    prompt = (((step.get("config") or {}).get(molecule) or {}).get("prompt") or {})
    return prompt.get("request") or "", prompt.get("task") or ""


def _molecule_config(step: dict, molecule: str) -> dict:
    config = (step.get("config") or {}).get(molecule)
    assert isinstance(config, dict)
    return config


def _assert_custom_step_prompt_covers_routes(workflow: dict, step: dict, molecule: str) -> None:
    request, _ = _prompt_pair(step, molecule)
    routes = [
        route
        for route in workflow.get("outputRoutes") or []
        if route.get("stepName") == step.get("name")
    ]
    assert routes
    for route in routes:
        workflow_group = route["workflowGroup"]
        workflow_field = route["workflowField"]
        output_key = route["outputKey"]
        field = workflow["extract"][workflow_group]["fields"][workflow_field]
        prompt = field["prompt"]
        assert output_key in request
        assert workflow_field in request
        assert prompt["description"] in request
        assert prompt["instructions"] in request
        assert prompt["type"] in request
        for identifier in prompt["identifiers"]:
            assert identifier in request


def _assert_standard_extract_prompts_are_preserved(extract: dict) -> None:
    field_count = 0
    for group_name, group_data in extract.items():
        if group_name.startswith("_") or group_name == "workflow":
            continue
        fields = group_data.get("fields") or {}
        for field_name, field in fields.items():
            prompt = field.get("prompt") or {}
            field_count += 1
            assert prompt.get("description"), f"{group_name}.{field_name} description"
            assert prompt.get("instructions"), f"{group_name}.{field_name} instructions"
            assert prompt.get("type"), f"{group_name}.{field_name} type"
            assert prompt.get("identifiers"), f"{group_name}.{field_name} identifiers"
    assert field_count


def test_custom_step_prompts_are_rendered_for_required_molecules(monkeypatch):
    """Compiled custom steps must persist rich runtime prompts, not generic fallback."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)

    workflow = build_workflow(_write(_custom_yaml_with_two_statement_fields()))
    step = _custom_step_by_name(workflow, "statement_labels")
    _assert_standard_extract_prompts_are_preserved(workflow["extract"])

    for molecule in _required_prompt_molecules():
        config = _molecule_config(step, molecule)
        request, task = _prompt_pair(step, molecule)
        assert config["includes"] == {"pageImages": True}
        assert request
        assert task
        assert request.startswith("\n# Request")
        assert "# Extraction Guidelines" in request
        assert "# Field Descriptions" in request
        assert "# Output Contract" in request
        assert "# Final Notes" in request
        assert "account_number" in request
        assert "plan_name" in request
        assert "account identifier" in request
        assert "plan display name" in request
        assert "extract account exactly as written" in request
        assert "Extract only statement identity fields." in request
        assert "If you cannot identify a field with confidence" in request
        assert "Only return the JSON object" in request
        assert "empty string" not in request
        _assert_custom_step_prompt_covers_routes(workflow, step, molecule)
        assert task.startswith("\n# Identity")
        assert "# Process" in task
        assert "# Examples" in task
        assert "account_number" in task
        assert "plan_name" in task
        assert "structured-data extraction assistant" in task
        assert "extraneous commentary or text will break" in task


def test_custom_step_prompts_use_final_metadata_for_pseudo_groups(monkeypatch):
    """Pseudo prompts inherit final field prompt metadata plus pseudo instructions."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_identity
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  fields:
    account_number:
      prompt:
        description: final account identifier
        type: str
        identifiers: ["Account"]
        instructions: use the final field instructions
_pseudo_groups:
  statement_identity:
    workflow_step: statement_identity
    prompt:
      instructions: Extract identity fields only.
    fields:
      f001_account_number:
        path: /statement/account_number
"""

    workflow = build_workflow(_write(y))
    step = _custom_step_by_name(workflow, "statement_identity")

    for molecule in ("all", "paragraph"):
        request, task = _prompt_pair(step, molecule)
        assert "f001_account_number" in request
        assert "final account identifier" in request
        assert "use the final field instructions" in request
        assert "Extract identity fields only." in request
        assert "f001_account_number" in task


def test_pseudo_field_prompt_override_uses_full_prompt_shape(monkeypatch):
    """A pseudo field can override the final prompt when it uses full prompt shape."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_identity
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  fields:
    account_number:
      prompt:
        description: final account identifier
        type: str
        identifiers: ["Account"]
        instructions: use the final field instructions
_pseudo_groups:
  statement_identity:
    workflow_step: statement_identity
    fields:
      f001_account_number:
        path: /statement/account_number
        prompt:
          description: pseudo account identifier
          type: str
          identifiers: ["Account #"]
          instructions: use the pseudo override instructions
"""

    workflow = build_workflow(_write(y))

    prompt = workflow["extract"]["statement_identity"]["fields"]["f001_account_number"]["prompt"]
    assert prompt["description"] == "pseudo account identifier"
    step = _custom_step_by_name(workflow, "statement_identity")
    request, _ = _prompt_pair(step, "all")
    assert "pseudo account identifier" in request
    assert "use the pseudo override instructions" in request
    assert "final account identifier" not in request


def test_pseudo_field_prompt_override_requires_full_prompt_shape(monkeypatch):
    """Pseudo prompt overrides follow the same prompt schema as final fields."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_identity
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  fields:
    account_number:
      prompt:
        description: final account identifier
        type: str
        identifiers: ["Account"]
        instructions: use the final field instructions
_pseudo_groups:
  statement_identity:
    workflow_step: statement_identity
    fields:
      f001_account_number:
        path: /statement/account_number
        prompt:
          description: pseudo account identifier
          type: str
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "_pseudo_groups.statement_identity.f001_account_number.prompt" in message
    assert "identifiers" in message
    assert "instructions" in message


def test_custom_step_prompt_preserves_authored_molecule_override(monkeypatch):
    """Authored prompt config wins for that molecule; missing molecules are generated."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = _custom_yaml_with_two_statement_fields().replace(
        "      kind: instruct\n",
        """      kind: instruct
      config:
        paragraph:
          prompt:
            request: authored request
            task: authored task
""",
        1,
    )

    workflow = build_workflow(_write(y))
    step = _custom_step_by_name(workflow, "statement_labels")

    assert _prompt_pair(step, "paragraph") == ("authored request", "authored task")
    for molecule in ("all", "figure", "table-figure"):
        request, task = _prompt_pair(step, molecule)
        assert "account_number" in request
        assert "plan_name" in request
        assert task


def test_custom_step_type_rejects_multiple_workflow_groups(monkeypatch):
    """One custom step/type cannot merge multiple workflow group prompts implicitly."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
          chain: [reconcile_statement, qa_statement]
        - group: statement_totals
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
    total_due:
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
_pseudo_groups:
  statement_identity:
    workflow_step: statement_labels
    fields:
      account_number:
        path: /statement/account_number
  statement_totals:
    workflow_step: statement_labels
    fields:
      total_due:
        path: /statement/total_due
"""

    with pytest.raises(ValueError, match="one workflow group per custom step"):
        build_workflow(_write(y))


def test_sdk_and_fallback_prepare_render_same_custom_step_prompts(monkeypatch):
    """SDK-prepared and fallback-prepared groups must feed the same wrapper inputs."""
    yaml_text = _custom_yaml_with_two_statement_fields()
    yaml_path = _write(yaml_text)

    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    fallback = build_workflow(yaml_path)

    def _sdk_prepare(raw: str, **_kwargs):
        loaded = compile_workflow._safe_load_yaml(raw, "sdk")
        return compile_workflow._prepare_extraction_yaml_fallback(loaded, "sdk")

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        _sdk_prepare,
        raising=False,
    )
    sdk = build_workflow(yaml_path)

    for molecule in _required_prompt_molecules():
        fallback_prompt = _prompt_pair(
            _custom_step_by_name(fallback, "statement_labels"),
            molecule,
        )
        sdk_prompt = _prompt_pair(
            _custom_step_by_name(sdk, "statement_labels"),
            molecule,
        )
        assert fallback_prompt == sdk_prompt
        assert "account identifier" in fallback_prompt[0]
        assert "plan display name" in fallback_prompt[0]


def test_fallback_group_include_expands_defs_before_routing(monkeypatch):
    """Offline fallback must match SDK _defs/include behavior for final groups."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
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
  workflow_step: statement_labels
  fields:
    total_due:
      workflow_output_key: total_due
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
"""

    wf = build_workflow(_write(y))

    assert set(wf["extract"]["statement"]["fields"]) == {"account_number", "total_due"}
    assert {route["workflowField"] for route in wf["outputRoutes"]} == {
        "account_number",
        "total_due",
    }


def test_sdk_and_fallback_include_expansion_have_same_route_coverage(monkeypatch):
    """SDK-prepared and fallback-prepared include expansion must agree."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
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
  workflow_step: statement_labels
  fields:
    total_due:
      workflow_output_key: total_due
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
"""
    yaml_path = _write(y)

    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    fallback = build_workflow(yaml_path)

    def _sdk_prepare(raw: str, **_kwargs):
        loaded = compile_workflow._safe_load_yaml(raw, "sdk")
        return compile_workflow._prepare_extraction_yaml_fallback(loaded, "sdk")

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        _sdk_prepare,
        raising=False,
    )
    sdk = build_workflow(yaml_path)

    assert sdk["extract"]["statement"]["fields"] == fallback["extract"]["statement"]["fields"]
    assert sdk["outputRoutes"] == fallback["outputRoutes"]
    assert sdk["leafFields"] == fallback["leafFields"]


@pytest.mark.parametrize(
    ("defs_yaml", "group_include", "group_fields_yaml", "match"),
    [
        (
            """
  identity_fields:
    fields:
      account_number:
        workflow_output_key: account_number
        prompt:
          description: account
          type: str
          identifiers: ["Account"]
          instructions: extract account
""",
            "missing_fields",
            """
    total_due:
      workflow_output_key: total_due
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
""",
            "unknown _defs include \\[missing_fields\\]",
        ),
        (
            """
  a:
    include: b
    fields: {}
  b:
    include: a
    fields: {}
""",
            "a",
            """
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
""",
            "cyclic _defs include \\[a -> b -> a\\]",
        ),
        (
            """
  identity_fields:
    fields:
      account_number:
        workflow_output_key: account_number
        prompt:
          description: account
          type: str
          identifiers: ["Account"]
          instructions: extract account
""",
            "identity_fields",
            """
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account duplicate
        type: str
        identifiers: ["Account"]
        instructions: extract duplicate
""",
            "duplicate final field name \\[statement.account_number\\]",
        ),
        (
            """
  identity_fields:
    prompt: not allowed
    fields:
      account_number:
        workflow_output_key: account_number
        prompt:
          description: account
          type: str
          identifiers: ["Account"]
          instructions: extract account
""",
            "identity_fields",
            """
    total_due:
      workflow_output_key: total_due
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
""",
            "unsupported _defs keys",
        ),
    ],
)
def test_fallback_rejects_invalid_defs_include(
    monkeypatch,
    defs_yaml,
    group_include,
    group_fields_yaml,
    match,
):
    """Invalid _defs/include source fails before workflow JSON is produced."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = f"""
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
_defs:
{defs_yaml.rstrip()}
statement:
  include: {group_include}
  workflow_step: statement_labels
  fields:
{group_fields_yaml.rstrip()}
"""

    with pytest.raises(ValueError, match=match):
        build_workflow(_write(y))


def test_fallback_rejects_pseudo_group_include(monkeypatch):
    """Pseudo groups route workflow aliases; include belongs on final groups only."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
          chain: [reconcile_statement, qa_statement]
    - save_statement
_defs:
  identity_fields:
    fields:
      account_number:
        prompt:
          description: account
          type: str
          identifiers: ["Account"]
          instructions: extract account
statement:
  fields:
    account_number:
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
_pseudo_groups:
  statement_identity:
    include: identity_fields
    workflow_step: statement_labels
    fields:
      account_number:
        path: /statement/account_number
"""

    with pytest.raises(ValueError, match="pseudo group 'statement_identity'.*include"):
        build_workflow(_write(y))


def test_fallback_rejects_nested_final_field_paths(monkeypatch):
    """Runtime route parsing currently supports only /group/field final paths."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    plan:
      fields:
        name:
          workflow_output_key: plan_name
          prompt:
            description: plan
            type: str
            identifiers: ["Plan"]
            instructions: extract plan
"""

    with pytest.raises(ValueError, match="nested final fields"):
        build_workflow(_write(y))


def test_custom_workflow_rejects_field_level_workflow_step():
    """Split/recombine must use pseudo groups, not field-level workflow_step."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_step: statement_labels
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "field 'statement.account_number'" in message
    assert "field-level `workflow_step`" in message


def test_custom_workflow_rejects_hybrid_direct_and_pseudo_routing():
    """A final group cannot be routed directly and through pseudo groups."""
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
_pseudo_groups:
  statement_identity:
    workflow_step: statement_labels
    fields:
      account_number:
        path: /statement/account_number
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "routed by `_pseudo_groups`" in message
    assert "also declares direct `workflow_step:`" in message


def test_custom_workflow_rejects_unrouted_pseudo_final_field(monkeypatch):
    """Pseudo groups must cover every final leaf field they are replacing."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement_identity
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
    total_due:
      prompt:
        description: total
        type: float
        identifiers: ["Total"]
        instructions: extract total
_pseudo_groups:
  statement_identity:
    workflow_step: statement_labels
    fields:
      account_number:
        path: /statement/account_number
"""

    with pytest.raises(ValueError) as exc:
        build_workflow(_write(y))

    message = str(exc.value)
    assert "final group 'statement'" in message
    assert "not routed" in message
    assert "/statement/total_due" in message


def _prepared(workflow_slots):
    workflow_groups = {
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
        "statement_totals": {
            "fields": {
                "total_due": {
                    "prompt": {
                        "description": "total",
                        "type": "float",
                        "identifiers": ["Total"],
                        "instructions": "extract total",
                    }
                }
            }
        },
        "customer_packet": {
            "fields": {
                "customer_name": {
                    "prompt": {
                        "description": "customer",
                        "type": "str",
                        "identifiers": ["Name"],
                        "instructions": "extract customer",
                    }
                },
                "service_street": {
                    "prompt": {
                        "description": "street",
                        "type": "str",
                        "identifiers": ["Service Address"],
                        "instructions": "extract service street",
                    }
                }
            }
        },
    }
    return types.SimpleNamespace(
        groups={
            "statement": {
                "fields": {
                    "account_number": {
                        "prompt": {
                            "description": "account",
                            "type": "str",
                            "identifiers": ["Account"],
                            "instructions": "extract account",
                        }
                    },
                    "total_due": {
                        "prompt": {
                            "description": "total",
                            "type": "float",
                            "identifiers": ["Total"],
                            "instructions": "extract total",
                        }
                    },
                }
            },
            "customer": {
                "fields": {
                    "customer_name": {
                        "prompt": {
                            "description": "customer",
                            "type": "str",
                            "identifiers": ["Name"],
                            "instructions": "extract customer",
                        }
                    }
                }
            },
            "service_address": {
                "fields": {
                    "street": {
                        "prompt": {
                            "description": "street",
                            "type": "str",
                            "identifiers": ["Service Address"],
                            "instructions": "extract service street",
                        }
                    }
                }
            },
        },
        workflow_groups=workflow_groups,
        pseudo_groups={"statement_identity": {}, "statement_totals": {}, "customer_packet": {}},
        workflow_field_paths={
            "statement_identity": {"account_number": "/statement/account_number"},
            "statement_totals": {"total_due": "/statement/total_due"},
            "customer_packet": {
                "customer_name": "/customer/customer_name",
                "service_street": "/service_address/street",
            },
        },
        top_level_metadata={"domain": "custom"},
        final_group_metadata={"statement": {"unique_attrs": ["account_number"]}},
        workflow_group_metadata={name: {"slot": slot} for name, slot in workflow_slots.items()},
        persisted_workflow_extract=copy.deepcopy(workflow_groups),
    )


def _custom_prepared():
    workflow_groups = {
        "line_items": {
            "fields": {
                "description": {
                    "prompt": {
                        "description": "description",
                        "type": "str",
                        "identifiers": ["Description"],
                        "instructions": "extract description",
                    }
                }
            }
        }
    }
    persisted = copy.deepcopy(workflow_groups)
    persisted["workflow"] = {
        "metadata_version": 1,
        "template": {"BILLING_HINT": "Prefer charge table values."},
        "custom_steps": [
            {
                "name": "line_item_labels",
                "level": "chunk",
                "kind": "keys",
                "required_template_keys": ["BILLING_HINT"],
                "config": {"all": {"includes": {"text": True}}},
            }
        ],
        "agent_chain": [
            {
                "parallel": [
                    {
                        "group": "line_items",
                        "chain": ["reconcile_statement", "qa_statement"],
                    }
                ]
            },
            "save_statement",
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
                "readback_path": "/chunks/*/customChunkOutputs/line_item_labels/label",
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
        "field_counts": {"line_item_labels": 1},
    }
    # Derive schema_hash from the (already-normalized) leaves so it always equals
    # _custom_workflow_schema_hash(shipped metadata) — independent of how
    # repetition_scope is represented (AGE-168 "item" enum + AGE-169 recompute).
    persisted["workflow"]["schema_hash"] = compile_workflow._custom_workflow_schema_hash(
        persisted["workflow"]
    )
    return types.SimpleNamespace(
        groups=workflow_groups,
        workflow_groups=workflow_groups,
        pseudo_groups={},
        workflow_field_paths={
            "line_items": {"description": "/line_items/*/description"},
        },
        top_level_metadata={},
        final_group_metadata={},
        workflow_group_metadata={"line_items": {"workflow_step": "line_item_labels"}},
        persisted_workflow_extract=persisted,
    )


def test_custom_workflow_steps_compile_to_sdk_metadata(monkeypatch):
    """SDK-prepared custom metadata becomes workflow create/update body fields."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: _custom_prepared(),
        raising=False,
    )

    wf = build_workflow(_write(_custom_yaml()))

    assert wf["template"] == {"BILLING_HINT": "Prefer charge table values."}
    assert wf["customSteps"][0]["name"] == "line_item_labels"
    assert wf["customSteps"][0]["requiredTemplateKeys"] == ["BILLING_HINT"]
    assert wf["customSteps"][0]["config"]["all"]["includes"] == {
        "text": True,
        "pageImages": True,
    }
    assert wf["customSteps"][0]["config"]["all"]["prompt"]["request"]
    _assert_standard_extract_prompts_are_preserved(wf["extract"])
    _assert_custom_step_prompt_covers_routes(
        wf,
        wf["customSteps"][0],
        "all",
    )
    assert wf["outputRoutes"][0]["readbackPath"] == (
        "/chunks/*/customChunkOutputs/line_item_labels/label"
    )
    assert wf["leafFields"][0]["repetitionScope"] == "item"
    assert wf["extract"]["workflow"]["custom_steps"][0]["name"] == "line_item_labels"
    assert _slots(wf) == []


def test_custom_workflow_disables_stock_extraction_defaults(monkeypatch):
    """Extraction custom steps must not inherit the runtime's stock summary prompts."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: _custom_prepared(),
        raising=False,
    )

    wf = build_workflow(_write(_custom_yaml()))

    for step_name in (
        "doc-summary",
        "doc-keys",
        "sect-summary",
        "sect-instruct",
        "chunk-summary",
        "chunk-instruct",
    ):
        assert step_name in wf["steps"]
        assert wf["steps"][step_name] is None


def test_repeated_custom_steps_compile_with_wildcard_routes(monkeypatch):
    """Repeating custom steps must emit repeated route metadata everywhere."""
    prepared = _custom_prepared()
    workflow_metadata = prepared.persisted_workflow_extract["workflow"]
    workflow_metadata["output_routes"][0]["final_path"] = "/line_items/description"
    workflow_metadata["leaf_fields"][0]["final_path"] = "/line_items/description"
    workflow_metadata["leaf_fields"][0]["is_repeated"] = False
    workflow_metadata["leaf_fields"][0]["repetition_scope"] = "none"
    prepared.workflow_field_paths["line_items"]["description"] = "/line_items/description"

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )

    wf = build_workflow(_write(_custom_yaml()))

    route = wf["outputRoutes"][0]
    leaf = wf["leafFields"][0]
    persisted_route = wf["extract"]["workflow"]["output_routes"][0]
    persisted_leaf = wf["extract"]["workflow"]["leaf_fields"][0]

    assert route["finalPath"] == "/line_items/*/description"
    assert leaf["finalPath"] == "/line_items/*/description"
    assert leaf["isRepeated"] is True
    assert leaf["repetitionScope"] == "item"
    assert persisted_route["final_path"] == "/line_items/*/description"
    assert persisted_leaf["final_path"] == "/line_items/*/description"
    assert persisted_leaf["is_repeated"] is True
    assert persisted_leaf["repetition_scope"] == "item"


def test_repeated_group_shipped_schema_hash_matches_normalized_leaves(monkeypatch):
    """AGE-169: shipped schema_hash must match _custom_workflow_schema_hash(shipped leaves).

    Before the fix, schema_hash was computed before normalization (repetition_scope="none",
    no wildcard in final_path) but shipped alongside the post-normalization leaves
    (repetition_scope="/line_items/*", final_path="/line_items/*/description").
    The SDK recomputes the hash at update_prompts() time and raises ValueError.
    """
    prepared = _custom_prepared()
    workflow_metadata = prepared.persisted_workflow_extract["workflow"]
    # Simulate pre-normalization state: leaf has no wildcard and scope="none"
    workflow_metadata["output_routes"][0]["final_path"] = "/line_items/description"
    workflow_metadata["leaf_fields"][0]["final_path"] = "/line_items/description"
    workflow_metadata["leaf_fields"][0]["is_repeated"] = False
    workflow_metadata["leaf_fields"][0]["repetition_scope"] = "none"
    # Recompute the stale hash that _prepare_extraction_yaml_fallback would store
    workflow_metadata["schema_hash"] = compile_workflow._custom_workflow_schema_hash(
        workflow_metadata
    )
    prepared.workflow_field_paths["line_items"]["description"] = "/line_items/description"

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )

    wf, _ = compile_workflow.build_workflow_artifacts(_write(_custom_yaml()), name="test")

    shipped_workflow = wf["extract"]["workflow"]
    shipped_hash = shipped_workflow["schema_hash"]
    recomputed_hash = compile_workflow._custom_workflow_schema_hash(shipped_workflow)

    assert shipped_hash == recomputed_hash, (
        f"shipped schema_hash {shipped_hash!r} does not match "
        f"hash recomputed over shipped leaves {recomputed_hash!r}; "
        "the SDK will raise ValueError: caller schema_hash does not match route metadata"
    )


def test_workflow_step_replaces_slot_for_new_yaml(monkeypatch):
    """New YAML uses workflow_step metadata and does not require legacy slot."""
    seen_kwargs = {}

    def _prepare(raw, **kwargs):
        seen_kwargs.update(kwargs)
        return _custom_prepared()

    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        _prepare,
        raising=False,
    )
    yaml_text = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: line_item_labels
      level: chunk
      kind: keys
  agent_chain:
    - parallel:
        - group: line_items
          chain: [reconcile_statement, qa_statement]
    - save_statement
line_items:
  workflow_step: line_item_labels
  fields:
    description:
      workflow_output_key: label
      prompt:
        description: description
        type: str
        identifiers: ["Description"]
        instructions: extract description
"""

    wf = build_workflow(_write(yaml_text))

    assert "workflow_step" in seen_kwargs["workflow_group_metadata_keys"]
    assert "slot" not in wf["extract"]["line_items"]
    assert wf["customSteps"][0]["name"] == "line_item_labels"


def test_slot_and_workflow_step_conflict_fails():
    """A group cannot use legacy slot and new workflow_step together."""
    yaml_text = """
workflow:
  custom_steps:
    - name: line_item_labels
      level: chunk
      kind: keys
line_items:
  slot: chunk-keys
  workflow_step: line_item_labels
  fields:
    description:
      workflow_output_key: label
      prompt:
        description: description
        type: str
        identifiers: ["Description"]
        instructions: extract description
"""

    with pytest.raises(ValueError, match="slot.*workflow_step|workflow_step.*slot"):
        build_workflow(_write(yaml_text))


def test_custom_workflow_compiles_without_sdk_helper(monkeypatch):
    """Offline validation must compile custom workflow syntax without groundx installed."""
    monkeypatch.setattr(compile_workflow, "_sdk_prepare_extraction_yaml", None, raising=False)
    y = _custom_yaml()

    wf = build_workflow(_write(y))

    assert wf["customSteps"][0]["name"] == "statement_labels"
    assert wf["outputRoutes"][0]["finalPath"] == "/statement/account_number"


def test_prepared_schema_without_custom_workflow_metadata_fails(monkeypatch):
    """Harness templates do not fall back to legacy slot compilation."""
    prepared = _custom_prepared()
    prepared.persisted_workflow_extract = None
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )

    with pytest.raises(ValueError, match="workflow\\.custom_steps"):
        compile_workflow.build_workflow_artifacts(_write(_custom_yaml()), name="test")


def test_build_workflow_consumes_prepared_workflow_groups(monkeypatch):
    """Prepared metadata without custom workflow settings is rejected."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: _prepared(
            {
                "statement_identity": "chunk-instruct",
                "statement_totals": "chunk-summary",
                "customer_packet": "chunk-keys",
            }
        ),
        raising=False,
    )
    y = "statement:\n  fields:\n" + _F.format(name="account_number")
    with pytest.raises(ValueError, match="extraction_policy_version: v1"):
        build_workflow(_write(y))


def test_build_workflow_allows_prepared_groups_to_share_slot(monkeypatch):
    """Custom workflow metadata bypasses legacy slot compilation."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: _custom_prepared(),
        raising=False,
    )
    wf = build_workflow(_write(_custom_yaml()))
    assert _slots(wf) == []
    assert wf["customSteps"][0]["name"] == "line_item_labels"


def test_build_workflow_artifacts_emit_reassembly_metadata(monkeypatch):
    """Metadata preserves split and merge routes back to final output groups."""
    prepared = _custom_prepared()
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )
    path = _write(_custom_yaml())
    _, metadata = compile_workflow.build_workflow_artifacts(path, name="test")
    assert metadata["schema_version"] == "extraction_workflow_metadata_v1"
    assert metadata["workflow_field_paths"] == prepared.workflow_field_paths
    assert metadata["workflow_field_paths"]["line_items"] == {
        "description": "/line_items/*/description"
    }
    assert metadata["prepared_final_groups"] == prepared.groups
    assert metadata["final_group_metadata"] == prepared.final_group_metadata
    assert metadata["workflow_group_metadata"] == prepared.workflow_group_metadata


def test_build_workflow_artifacts_use_sdk_persisted_extract(monkeypatch):
    """Compiled workflow.extract preserves authored YAML metadata."""
    prepared = _custom_prepared()
    workflow_metadata = copy.deepcopy(prepared.persisted_workflow_extract["workflow"])
    prepared.persisted_workflow_extract = copy.deepcopy(prepared.workflow_groups)
    prepared.persisted_workflow_extract["workflow"] = workflow_metadata
    prepared.persisted_workflow_extract["_groundx_persisted_extract"] = {
        "extraction_policy_version": "v1",
        "workflow": copy.deepcopy(workflow_metadata),
        "line_items": {
            "workflow_step": "line_item_labels",
            "match_attrs": ["description"],
            "explanation_attrs": ["description_explanation"],
            "fields": {"description": {"prompt": {"description": "description"}}},
        },
    }
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )

    wf, _ = compile_workflow.build_workflow_artifacts(
        _write(_custom_yaml()),
        name="test",
    )

    assert wf["extract"]["line_items"] == prepared.persisted_workflow_extract["line_items"]
    assert {"line_items", "_groundx_persisted_extract"}.issubset(wf["extract"])
    authored = wf["extract"]["_groundx_persisted_extract"]
    assert authored["extraction_policy_version"] == "v1"
    assert authored["line_items"]["workflow_step"] == "line_item_labels"
    assert authored["line_items"]["match_attrs"] == ["description"]
    assert authored["line_items"]["explanation_attrs"] == ["description_explanation"]
    assert authored["workflow"] == wf["extract"]["workflow"]
    persisted_step = wf["extract"]["workflow"]["custom_steps"][0]
    _assert_standard_extract_prompts_are_preserved(wf["extract"])
    for molecule in _required_prompt_molecules():
        prompt = persisted_step["config"][molecule]["prompt"]
        assert "# Extraction Guidelines" in prompt["request"]
        assert "# Output Contract" in prompt["request"]
        assert "Only return the JSON array" in prompt["request"]
        assert "description" in prompt["request"]
        assert "extract description" in prompt["request"]
        assert "structured-data extraction assistant" in prompt["task"]


def test_fallback_prepare_preserves_agent_chain(monkeypatch):
    """Offline fallback must preserve the same agent_chain metadata as the SDK."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    yaml_text = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""
    expected_chain = [
        {
            "parallel": [
                {
                    "group": "statement",
                    "chain": ["reconcile_statement", "qa_statement"],
                }
            ]
        },
        "save_statement",
    ]

    wf = build_workflow(_write(yaml_text))

    assert wf["extract"]["workflow"]["agent_chain"] == expected_chain
    authored = wf["extract"]["_groundx_persisted_extract"]
    assert authored["workflow"]["agent_chain"] == expected_chain


def test_fallback_agent_chain_does_not_change_schema_hash(monkeypatch):
    """agent_chain is runtime metadata; cashbot validates the route schema hash."""
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    base_yaml = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""
    chained_yaml = base_yaml.replace(
        """  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
""",
        """  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
""",
    )

    base = build_workflow(_write(base_yaml))
    chained = build_workflow(_write(chained_yaml))

    assert (
        base["extract"]["workflow"]["schema_hash"]
        == chained["extract"]["workflow"]["schema_hash"]
    )


def test_fallback_agent_chain_rejects_chain_without_initial_parallel_stage(monkeypatch):
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    yaml_text = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""

    with pytest.raises(
        ValueError,
        match="workflow.agent_chain must start with a parallel stage",
    ):
        build_workflow(_write(yaml_text))


def test_fallback_agent_chain_rejects_branch_save_plus_top_level_save(monkeypatch):
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    yaml_text = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""

    with pytest.raises(
        ValueError,
        match="parallel branch save tasks cannot be combined",
    ):
        build_workflow(_write(yaml_text))


def test_fallback_agent_chain_rejects_invalid_top_level_serial_task_pairs(monkeypatch):
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    base_yaml = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
  agent_chain:
{agent_chain}
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
"""
    cases = [
        """
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
    - reconcile_charges
""",
        """
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement, save_statement]
    - reconcile_charges
    - save_statement
""",
        """
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
    - reconcile_charges
""",
    ]

    for agent_chain in cases:
        with pytest.raises(ValueError, match="top-level agent task"):
            build_workflow(_write(base_yaml.format(agent_chain=agent_chain)))


def test_fallback_agent_chain_rejects_unscheduled_workflow_groups(monkeypatch):
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        None,
        raising=False,
    )
    yaml_text = """
extraction_policy_version: v1
workflow:
  custom_steps:
    - name: statement_labels
      level: chunk
      kind: instruct
    - name: meter_labels
      level: chunk
      kind: summary
    - name: charge_labels
      level: chunk
      kind: keys
  agent_chain:
    - parallel:
        - group: statement
          chain: [reconcile_statement, qa_statement]
    - save_statement
statement:
  workflow_step: statement_labels
  fields:
    account_number:
      workflow_output_key: account_number
      prompt:
        description: account
        type: str
        identifiers: ["Account"]
        instructions: extract account
meters:
  workflow_step: meter_labels
  fields:
    meter_number:
      workflow_output_key: meter_number
      prompt:
        description: meter
        type: str
        identifiers: ["Meter"]
        instructions: extract meter
charges:
  workflow_step: charge_labels
  fields:
    charge_amount:
      workflow_output_key: charge_amount
      prompt:
        description: charge
        type: float
        identifiers: ["Charge"]
        instructions: extract charge
"""

    with pytest.raises(
        ValueError,
        match="does not cover workflow groups .*charges.*meters",
    ):
        build_workflow(_write(yaml_text))


def test_compile_cli_writes_sdk_persisted_extract(monkeypatch, capsys):
    """The CLI stdout workflow JSON preserves and normalizes persisted extract."""
    prepared = _custom_prepared()
    workflow_metadata = copy.deepcopy(prepared.persisted_workflow_extract["workflow"])
    prepared.persisted_workflow_extract = copy.deepcopy(prepared.workflow_groups)
    prepared.persisted_workflow_extract["workflow"] = workflow_metadata
    prepared.persisted_workflow_extract["_groundx_persisted_extract"] = {
        "extraction_policy_version": "v1",
        "workflow": copy.deepcopy(workflow_metadata),
        "line_items": {"workflow_step": "line_item_labels"},
    }
    monkeypatch.setattr(
        compile_workflow,
        "_sdk_prepare_extraction_yaml",
        lambda raw, **kwargs: prepared,
        raising=False,
    )
    yaml_path = _write(_custom_yaml())
    monkeypatch.setattr(sys, "argv", ["compile_workflow.py", yaml_path, "--name", "test"])

    assert compile_workflow.main() == 0
    workflow = json.loads(capsys.readouterr().out)

    assert workflow["extract"]["line_items"] == prepared.persisted_workflow_extract["line_items"]
    authored = workflow["extract"]["_groundx_persisted_extract"]
    assert authored["line_items"] == {"workflow_step": "line_item_labels"}
    assert authored["workflow"] == workflow["extract"]["workflow"]
    persisted_step = workflow["extract"]["workflow"]["custom_steps"][0]
    assert persisted_step["config"]["all"]["prompt"]["request"]
    assert persisted_step["config"]["figure"]["prompt"]["request"]


def test_deploy_compile_artifact_preserves_persisted_extract(tmp_path):
    """Deploy dry-run compile writes the same persisted extract to workflow.json."""
    yaml_path = _write(_custom_yaml())

    workflow = deploy_workflow._compile_workflow(
        yaml_path,
        workflow_name="test",
        out=str(tmp_path),
        skip_validate=True,
    )
    with open(tmp_path / "workflow.json", encoding="utf-8") as f:
        written = json.load(f)

    assert written["extract"] == workflow["extract"]
    assert "workflow" in written["extract"]
    assert written["customSteps"]


def test_deploy_create_and_update_send_compiled_extract_verbatim():
    """Deploy request bodies must use the compiled persisted extract unchanged."""

    class _Workflows:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(("create", kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id="created"))

        def update(self, workflow_id, **kwargs):
            self.calls.append(("update", workflow_id, kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id=workflow_id))

    gx = types.SimpleNamespace(workflows=_Workflows())
    workflow = _workflow_with_persisted_extract()

    deploy_workflow._create_or_update_workflow(
        gx,
        workflow,
        yaml_path="statement.yaml",
        workflow_id=None,
    )
    deploy_workflow._create_or_update_workflow(
        gx,
        workflow,
        yaml_path="statement.yaml",
        workflow_id="wf-1",
    )

    assert gx.workflows.calls[0][1]["extract"] is workflow["extract"]
    assert gx.workflows.calls[1][2]["extract"] is workflow["extract"]
    assert gx.workflows.calls[0][1]["section_strategy"] == workflow["section_strategy"]
    assert gx.workflows.calls[1][2]["section_strategy"] == workflow["section_strategy"]
    assert gx.workflows.calls[0][1]["template"] is workflow["template"]
    assert gx.workflows.calls[0][1]["custom_steps"] is workflow["customSteps"]
    assert gx.workflows.calls[0][1]["output_routes"] is workflow["outputRoutes"]
    assert gx.workflows.calls[0][1]["leaf_fields"] is workflow["leafFields"]
    assert gx.workflows.calls[1][2]["template"] is workflow["template"]
    assert gx.workflows.calls[1][2]["custom_steps"] is workflow["customSteps"]
    assert gx.workflows.calls[1][2]["output_routes"] is workflow["outputRoutes"]
    assert gx.workflows.calls[1][2]["leaf_fields"] is workflow["leafFields"]


def test_custom_workflow_preserves_section_strategy_in_workflow_and_extract():
    workflow = build_workflow(_write(_custom_yaml_with_section_strategy()))

    assert workflow["section_strategy"] == "page"
    assert workflow["extract"]["workflow"]["section_strategy"] == "page"


def test_deploy_create_and_update_use_compiled_payload_when_helpers_exist():
    class _Workflows:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(("create", kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id="created"))

        def update(self, workflow_id, **kwargs):
            self.calls.append(("update", workflow_id, kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id=workflow_id))

    class _GroundX:
        def __init__(self):
            self.workflows = _Workflows()

        def create_extraction_workflow(self, **kwargs):
            raise AssertionError("compiled deploy path should not re-load raw YAML path")

        def update_extraction_workflow(self, workflow_id, **kwargs):
            raise AssertionError("compiled deploy path should not re-load raw YAML path")

    gx = _GroundX()
    workflow = _workflow_with_persisted_extract()

    deploy_workflow._create_or_update_workflow(
        gx,
        workflow,
        yaml_path="statement.yaml",
        workflow_id=None,
    )
    deploy_workflow._create_or_update_workflow(
        gx,
        workflow,
        yaml_path="statement.yaml",
        workflow_id="wf-1",
    )

    assert gx.workflows.calls[0][1]["extract"] is workflow["extract"]
    assert gx.workflows.calls[1][2]["extract"] is workflow["extract"]


def test_run_and_batch_create_workflow_use_compiled_payload_when_helpers_exist():
    class _Workflows:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id="created"))

    class _GroundX:
        def __init__(self):
            self.workflows = _Workflows()

        def create_extraction_workflow(self, **kwargs):
            raise AssertionError("compiled run path should not re-load raw YAML path")

    workflow = _workflow_with_persisted_extract()

    run_gx = _GroundX()
    run_extraction._create_workflow(run_gx, "statement.yaml", workflow, "test")
    batch_gx = _GroundX()
    batch_extraction._create_workflow(batch_gx, "statement.yaml", workflow, "test")

    assert run_gx.workflows.calls[0]["extract"] is workflow["extract"]
    assert batch_gx.workflows.calls[0]["extract"] is workflow["extract"]


def test_prompt_manager_create_update_use_compiled_payload_when_helpers_exist(monkeypatch):
    workflow = _workflow_with_persisted_extract()
    monkeypatch.setattr(
        prompt_manager,
        "build_workflow",
        lambda yaml_path, name=None: workflow,
    )

    class _Workflows:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(("create", kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id="created"))

        def update(self, id, **kwargs):
            self.calls.append(("update", id, kwargs))
            return types.SimpleNamespace(workflow=types.SimpleNamespace(workflow_id=id))

    class _GroundX:
        def __init__(self):
            self.workflows = _Workflows()

        def create_extraction_workflow(self, **kwargs):
            raise AssertionError("compiled manager path should not re-load raw YAML path")

        def update_extraction_workflow(self, workflow_id, **kwargs):
            raise AssertionError("compiled manager path should not re-load raw YAML path")

    gx = _GroundX()
    manager = prompt_manager.ExtractionWorkflowManager(gx)

    assert manager.init_prompts(yaml_path="statement.yaml") == "created"
    assert manager.update_prompts(workflow_id="wf-1", yaml_path="statement.yaml") == "wf-1"
    assert gx.workflows.calls[0][1]["extract"] is workflow["extract"]
    assert gx.workflows.calls[1][2]["extract"] is workflow["extract"]


def test_prompt_manager_exposes_persisted_workflow_extract_dict(monkeypatch):
    workflow = _workflow_with_persisted_extract()
    monkeypatch.setattr(
        prompt_manager,
        "build_workflow",
        lambda yaml_path, name=None: workflow,
    )

    manager = prompt_manager.ExtractionWorkflowManager(types.SimpleNamespace())

    assert (
        manager.persisted_workflow_extract_dict(yaml_path="statement.yaml")
        is workflow["extract"]
    )


def test_run_compile_artifact_preserves_persisted_extract(tmp_path):
    """Run path compile writes the same persisted extract to workflow.json."""

    class _RunLog:
        def event(self, *args, **kwargs):
            return None

    yaml_path = _write(_custom_yaml())
    workflow_json_path = tmp_path / "workflow.json"

    workflow = run_extraction._compile(
        yaml_path,
        str(workflow_json_path),
        name="test",
        rl=_RunLog(),
    )
    with open(workflow_json_path, encoding="utf-8") as f:
        written = json.load(f)

    assert written["extract"] == workflow["extract"]
    assert "workflow" in written["extract"]
    assert written["customSteps"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
