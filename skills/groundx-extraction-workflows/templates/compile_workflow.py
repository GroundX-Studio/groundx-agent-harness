#!/usr/bin/env python3
"""Compile a YAML extraction schema into a GroundX workflow JSON.

Usage:
    python compile_workflow.py <prompt.yaml> [--name NAME] > workflow.json

Outputs the workflow JSON to stdout. Does NOT call any GroundX API —
this is a pure offline transformation. The output is the exact body
shape you POST to `/v1/workflow` (or pass to `gx.workflows.create()`,
or to the `workflow_create` MCP tool from the groundx-api skill).

Domain-agnostic custom workflow mapping
---------------------------------------
The compiler carries no hardcoded final group names. Top-level real YAML groups
define the final data object. Harness-authored YAML has two workflow shapes:
direct real groups with group-level `workflow_step:`, or `_pseudo_groups` that
split oversized final groups into smaller workflow-only groups and route back
to final fields with `path`.

Older `domain:` and `slot:` YAMLs are intentionally rejected here. Harness
templates author the v1 shape only. Field-level `workflow_step` is also rejected
because split/recombine belongs in `_pseudo_groups`.

Reads .env for EXTRACT_MODEL_* (engine config) when python-dotenv is installed.
No real GROUNDX_API_KEY is needed because no API calls are made; a placeholder
is acceptable.

For the actual API calls (workflow create, attach to bucket, ingest,
poll, retrieve extract), use the groundx-api skill — that is the
source of truth for those operations.
"""

import argparse
import copy
import dataclasses
import hashlib
import json
import os
import sys
import typing

import yaml

# Resolve .env from the user's cwd, not the script's __file__ tree.
try:
    import dotenv
except ImportError:
    dotenv = None

if dotenv is not None:
    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

try:
    from groundx import WorkflowSteps
except ImportError:
    WorkflowSteps = None

try:
    from groundx.extract import prepare_extraction_yaml as _sdk_prepare_extraction_yaml
except ImportError:
    _sdk_prepare_extraction_yaml = None


# Exactly the WorkflowSteps stage attrs the workflow JSON carries. Passed
# explicitly (None for unused) so the wire form is stable; this set is
# intentionally the same one the prior compiler emitted (no sect-keys /
# search-query) so existing workflows compile identically.
_ALL_STAGE_ATTRS = (
    "chunk_instruct",
    "chunk_keys",
    "chunk_summary",
    "doc_keys",
    "doc_summary",
    "sect_instruct",
    "sect_summary",
)

# Top-level YAML keys that are NOT final groups. Consumed locally during compile.
RESERVED_TOP_LEVEL_KEYS = {
    "extraction_policy_version",
    "workflow",
    "_defs",
    "_groundx_persisted_extract",
    "_pseudo_groups",
}
_SOURCE_RESERVED_TOP_LEVEL_KEYS = {
    "extraction_policy_version",
    "workflow",
    "_defs",
    "_pseudo_groups",
}
_GENERATED_WORKFLOW_TOP_LEVEL_KEYS = {
    "chunk_strategy",
    "chunkStrategy",
    "customSteps",
    "extract",
    "leafFields",
    "name",
    "outputRoutes",
    "section_strategy",
    "sectionStrategy",
    "steps",
    "workflowId",
    "workflow_id",
}
_SOURCE_WORKFLOW_KEYS = {
    "agent_chain",
    "custom_steps",
    "section_strategy",
    "template",
}
_CUSTOM_STEP_KEYS = {
    "config",
    "kind",
    "level",
    "name",
    "required_template_keys",
}

# Per-group keys consumed locally: custom workflow selectors plus client-side
# business-logic metadata applied by templates/business_logic.py after extraction.
_GROUP_METADATA_KEYS = {
    "workflow_step",
    "always_check_attrs",
    "conflict_attrs",
    "deregulation_status_values",
    "equivalent_service_types",
    "exclude_dict_attrs",
    "explanation_attrs",
    "fill_rules",
    "final_value_aliases",
    "match_attrs",
    "not_required_service_types",
    "partial_pair_attrs",
    "passthrough",
    "passthrough_attrs",
    "passthrough_pair_attrs",
    "remaining_attrs",
    "required_any_attrs",
    "required_attrs",
    "role",
    "unique_attrs",
}

_TOP_LEVEL_METADATA_KEYS = {"extraction_policy_version"}
_WORKFLOW_GROUP_METADATA_KEYS = {"workflow_step"}
_FINAL_GROUP_METADATA_KEYS = _GROUP_METADATA_KEYS - _WORKFLOW_GROUP_METADATA_KEYS
_PERSISTED_EXTRACT_REQUIRED_GROUP_KEYS = _GROUP_METADATA_KEYS
_CUSTOM_WORKFLOW_FIELD_METADATA_KEY = "workflow_output_key"
_DIRECT_FIELD_KEYS = {
    _CUSTOM_WORKFLOW_FIELD_METADATA_KEY,
    "fields",
    "prompt",
}
_PSEUDO_FIELD_KEYS = {"path", "prompt"}
_PROMPT_KEYS = {
    "default",
    "description",
    "format",
    "identifiers",
    "instructions",
    "type",
}
_REQUIRED_PROMPT_KEYS = {
    "description",
    "identifiers",
    "instructions",
    "type",
}
_CUSTOM_WORKFLOW_GROUP_FIELD_LIMIT = 30
_CUSTOM_WORKFLOW_OUTPUT_MAPS = {
    "chunk": "customChunkOutputs",
    "section": "customSectionOutputs",
    "document": "customDocumentOutputs",
}
_CUSTOM_WORKFLOW_AGENT_CHAIN_AGENT_TASKS = frozenset(
    {
        "reconcile_charges",
        "reconcile_meters",
        "reconcile_statement",
        "qa_meters",
        "qa_statement",
    }
)
_CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS = frozenset(
    {
        "save_charges",
        "save_meters",
        "save_statement",
    }
)
_CUSTOM_WORKFLOW_AGENT_CHAIN_SUPPORTED_TASKS = (
    _CUSTOM_WORKFLOW_AGENT_CHAIN_AGENT_TASKS | _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS
)
_CUSTOM_WORKFLOW_REPEATED_STEP_KINDS = {"keys", "summary"}
_CUSTOM_WORKFLOW_PROMPT_MOLECULE_KEYS = ("all", "figure", "paragraph", "table-figure")
_DISABLED_DEFAULT_EXTRACTION_STEPS = (
    "chunk-instruct",
    "chunk-summary",
    "doc-keys",
    "doc-summary",
    "sect-instruct",
    "sect-summary",
)
_EMPTY_WORKFLOW_STEP_KEYS = (
    "chunk-instruct",
    "chunk-keys",
    "chunk-summary",
    "doc-keys",
    "doc-summary",
    "search-query",
    "sect-instruct",
    "sect-keys",
    "sect-summary",
)


@dataclasses.dataclass
class _PreparedExtractionYaml:
    groups: dict
    workflow_groups: dict
    pseudo_groups: dict
    workflow_field_paths: dict
    persisted_workflow_extract: dict
    top_level_metadata: dict
    final_group_metadata: dict
    workflow_group_metadata: dict


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping_no_duplicates(
    loader: _NoDuplicateSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key == "<<":
            raise ValueError("YAML merge keys (`<<`) are not supported")
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)


def _assert_no_cycles(obj: typing.Any, path: str, active: typing.Optional[set[int]] = None) -> None:
    if active is None:
        active = set()
    if not isinstance(obj, (dict, list)):
        return
    oid = id(obj)
    if oid in active:
        raise ValueError(f"recursive YAML alias or cyclic graph at {path}")
    active.add(oid)
    if isinstance(obj, dict):
        for key, value in obj.items():
            _assert_no_cycles(value, f"{path}.{key}", active)
    else:
        for idx, value in enumerate(obj):
            _assert_no_cycles(value, f"{path}[{idx}]", active)
    active.remove(oid)


def _safe_load_yaml(text: str, source: str) -> typing.Any:
    try:
        data = yaml.load(text, Loader=_NoDuplicateSafeLoader)
    except yaml.constructor.ConstructorError as exc:
        if "recursive" in str(exc).lower():
            raise ValueError(f"{source}: recursive YAML alias or cyclic graph") from exc
        raise
    _assert_no_cycles(data, source)
    return data


def _workflow_group_items(raw: dict) -> typing.Iterator[tuple[str, dict]]:
    for group_name, group_data in raw.items():
        if group_name in RESERVED_TOP_LEVEL_KEYS:
            continue
        if isinstance(group_data, dict):
            yield str(group_name), group_data


def _raw_uses_custom_workflow_metadata(raw: dict) -> bool:
    if "workflow" in raw:
        return True
    return any("workflow_step" in group_data for _, group_data in _workflow_group_items(raw))


def _contains_include(obj: typing.Any) -> bool:
    if isinstance(obj, dict):
        if "include" in obj:
            return True
        return any(_contains_include(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_include(v) for v in obj)
    return False


def _ensure_mapping(value: typing.Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping at [{path}], got {type(value)}")
    return typing.cast(dict, value)


def _ensure_fields_mapping(value: typing.Any, path: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected fields mapping at [{path}], got {type(value)}")
    return typing.cast(dict, value)


def _normalize_include(value: typing.Any, path: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return typing.cast(list[str], value)
    raise ValueError(f"Expected string or string list at [{path}]")


def _merge_fields(target: dict, incoming: dict, path: str) -> None:
    for field_name, field_value in incoming.items():
        if field_name in target:
            raise ValueError(f"duplicate final field name [{path}.{field_name}]")
        target[field_name] = copy.deepcopy(field_value)


def _compose_def_fields(defs: dict, name: str, stack: tuple[str, ...]) -> dict:
    if name not in defs:
        raise ValueError(f"unknown _defs include [{name}]")
    if name in stack:
        cycle = " -> ".join([*stack, name])
        raise ValueError(f"cyclic _defs include [{cycle}]")

    fragment = _ensure_mapping(defs[name], f"_defs.{name}")
    unsupported = set(fragment) - {"include", "fields"}
    if unsupported:
        raise ValueError(
            f"unsupported _defs keys at [_defs.{name}]: {sorted(unsupported)}"
        )
    if "fields" not in fragment:
        raise ValueError(f"_defs.{name} must declare fields")

    fields: dict = {}
    for include_name in _normalize_include(fragment.get("include"), f"_defs.{name}.include"):
        _merge_fields(
            fields,
            _compose_def_fields(defs, include_name, (*stack, name)),
            f"_defs.{name}",
        )
    _merge_fields(
        fields,
        _ensure_fields_mapping(fragment.get("fields"), f"_defs.{name}.fields"),
        f"_defs.{name}",
    )
    return fields


def _compose_group_fields(group_name: str, group_data: dict, defs: dict) -> dict:
    group = copy.deepcopy(group_data)
    fields: dict = {}
    for include_name in _normalize_include(group.pop("include", None), f"{group_name}.include"):
        _merge_fields(fields, _compose_def_fields(defs, include_name, ()), group_name)
    _merge_fields(
        fields,
        _ensure_fields_mapping(group.get("fields"), f"{group_name}.fields"),
        group_name,
    )
    group["fields"] = fields
    return group


def _assert_required_v1_source_metadata(raw: dict, source: str) -> None:
    if raw.get("extraction_policy_version") != "v1":
        raise ValueError(
            f"{source}: harness source YAML must declare extraction_policy_version: v1"
        )

    workflow = raw.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError(f"{source}: workflow.custom_steps is required for harness workflow YAML")

    unsupported = set(workflow) - _SOURCE_WORKFLOW_KEYS
    if unsupported:
        raise ValueError(
            f"{source}: unsupported workflow keys: {sorted(unsupported)}"
        )

    custom_steps = workflow.get("custom_steps")
    if not isinstance(custom_steps, list) or not custom_steps:
        raise ValueError(f"{source}: workflow.custom_steps must be a non-empty list")

    agent_chain = workflow.get("agent_chain")
    if not isinstance(agent_chain, list) or not agent_chain:
        raise ValueError(f"{source}: workflow.agent_chain must be a non-empty list")


def _assert_source_top_level_shape(raw: dict, source: str) -> None:
    if "_groundx_persisted_extract" in raw:
        raise ValueError(
            f"{source}: `_groundx_persisted_extract` is generated workflow "
            "metadata. Compile from v1 source YAML, not from a persisted "
            "workflow payload or workflow readback."
        )

    for key, value in raw.items():
        if key in _SOURCE_RESERVED_TOP_LEVEL_KEYS:
            continue
        if key in _GENERATED_WORKFLOW_TOP_LEVEL_KEYS:
            if isinstance(value, dict) and "fields" in value:
                continue
            raise ValueError(
                f"{source}: top-level key '{key}' looks like generated workflow "
                "metadata. Compile from v1 source YAML, not workflow readback."
            )
        if not isinstance(value, dict):
            raise ValueError(
                f"{source}: top-level key '{key}' must be a final group mapping "
                "or one of extraction_policy_version, workflow, _defs, "
                "or _pseudo_groups."
            )


def _assert_custom_steps_shape(workflow: dict, source: str) -> None:
    custom_steps = workflow.get("custom_steps")
    if not isinstance(custom_steps, list) or not custom_steps:
        return

    names: set[str] = set()
    for index, step in enumerate(custom_steps):
        path = f"workflow.custom_steps[{index}]"
        if not isinstance(step, dict):
            raise ValueError(f"{source}: {path} must be a mapping")
        unsupported = set(step) - _CUSTOM_STEP_KEYS
        if unsupported:
            raise ValueError(
                f"{source}: unsupported {path} keys: {sorted(unsupported)}"
            )
        name = step.get("name")
        level = step.get("level")
        kind = step.get("kind")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{source}: {path}.name must be a non-empty string")
        if name in names:
            raise ValueError(f"{source}: duplicate custom step name [{name}]")
        names.add(name)
        if not isinstance(level, str) or level not in _CUSTOM_WORKFLOW_OUTPUT_MAPS:
            raise ValueError(f"{source}: {path}.level is invalid")
        if kind not in {"instruct", "keys", "summary"}:
            raise ValueError(f"{source}: {path}.kind is invalid")
        if "config" in step and not isinstance(step["config"], dict):
            raise ValueError(f"{source}: {path}.config must be a mapping")
        required_keys = step.get("required_template_keys")
        if required_keys is not None and (
            not isinstance(required_keys, list)
            or not all(isinstance(item, str) for item in required_keys)
        ):
            raise ValueError(
                f"{source}: {path}.required_template_keys must be a string list"
            )


def _assert_prompt_shape(prompt: typing.Any, path: str, source: str) -> None:
    if not isinstance(prompt, dict):
        raise ValueError(f"{source}: {path}.prompt must be a mapping")
    unsupported = set(prompt) - _PROMPT_KEYS
    if unsupported:
        raise ValueError(f"{source}: unsupported {path}.prompt keys: {sorted(unsupported)}")
    missing = sorted(_REQUIRED_PROMPT_KEYS - set(prompt))
    if missing:
        raise ValueError(f"{source}: {path}.prompt missing required keys: {missing}")


def _assert_group_prompt_shape(prompt: typing.Any, path: str, source: str) -> None:
    if prompt is not None and not isinstance(prompt, dict):
        raise ValueError(f"{source}: {path}.prompt must be a mapping")


def _assert_direct_field_shape(
    field_data: dict,
    path: str,
    source: str,
) -> None:
    if "workflow_step" in field_data:
        raise ValueError(
            f"{source}: field '{path}' uses field-level `workflow_step`. Put "
            "`workflow_step:` on a direct workflow group, or use "
            "`_pseudo_groups` with `path` routes for split/recombine."
        )
    unsupported = set(field_data) - _DIRECT_FIELD_KEYS
    if unsupported:
        raise ValueError(f"{source}: unsupported {path} keys: {sorted(unsupported)}")
    if "fields" in field_data:
        return
    _assert_prompt_shape(field_data.get("prompt"), path, source)


def _assert_pseudo_field_shape(
    field_data: dict,
    path: str,
    source: str,
) -> None:
    if "workflow_step" in field_data:
        raise ValueError(
            f"{source}: pseudo field '{path}' uses field-level "
            "`workflow_step`. Put `workflow_step:` on the pseudo group."
        )
    unsupported = set(field_data) - _PSEUDO_FIELD_KEYS
    if unsupported:
        raise ValueError(f"{source}: unsupported {path} keys: {sorted(unsupported)}")
    if "prompt" in field_data:
        _assert_prompt_shape(field_data.get("prompt"), path, source)


def _assert_source_group_shapes(raw: dict, source: str) -> None:
    allowed_group_keys = {"fields", "include", "prompt", "workflow_step"} | _FINAL_GROUP_METADATA_KEYS
    for group_name, group_data in _workflow_group_items(raw):
        unsupported = set(group_data) - allowed_group_keys
        if unsupported:
            raise ValueError(
                f"{source}: unsupported final group '{group_name}' keys: "
                f"{sorted(unsupported)}"
            )
        _assert_group_prompt_shape(group_data.get("prompt"), group_name, source)
        fields = group_data.get("fields")
        if fields is not None and not isinstance(fields, dict):
            raise ValueError(f"{source}: {group_name}.fields must be a mapping")
        if isinstance(fields, dict):
            for field_name, field_data in fields.items():
                if not isinstance(field_data, dict):
                    raise ValueError(
                        f"{source}: {group_name}.{field_name} must be a field mapping"
                    )
        for field_path, field_data in _walk_field_items(fields):
            _assert_direct_field_shape(
                field_data,
                ".".join((group_name, *field_path)),
                source,
            )

    pseudo_groups = raw.get("_pseudo_groups")
    if pseudo_groups is None:
        return
    if not isinstance(pseudo_groups, dict):
        raise ValueError(f"{source}: `_pseudo_groups` must be a mapping")
    for group_name, group_data in pseudo_groups.items():
        path = f"_pseudo_groups.{group_name}"
        if not isinstance(group_data, dict):
            raise ValueError(f"{source}: {path} must be a mapping")
        unsupported = set(group_data) - {"fields", "include", "prompt", "workflow_step"}
        if unsupported:
            raise ValueError(f"{source}: unsupported {path} keys: {sorted(unsupported)}")
        _assert_group_prompt_shape(group_data.get("prompt"), path, source)
        fields = group_data.get("fields")
        if fields is not None and not isinstance(fields, dict):
            raise ValueError(f"{source}: {path}.fields must be a mapping")
        for field_path, field_data in _walk_field_items(fields):
            _assert_pseudo_field_shape(
                field_data,
                ".".join((path, *field_path)),
                source,
            )


def _assert_def_field_shapes(defs: dict, source: str) -> None:
    for def_name, fragment in defs.items():
        if not isinstance(fragment, dict):
            continue
        fields = fragment.get("fields")
        if fields is None:
            continue
        if not isinstance(fields, dict):
            raise ValueError(f"{source}: _defs.{def_name}.fields must be a mapping")
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                raise ValueError(
                    f"{source}: _defs.{def_name}.{field_name} must be a field mapping"
                )
        for field_path, field_data in _walk_field_items(fields):
            _assert_direct_field_shape(
                field_data,
                ".".join((f"_defs.{def_name}", *field_path)),
                source,
            )


def _assert_no_pseudo_group_include(raw: dict, source: str) -> None:
    pseudo_groups = raw.get("_pseudo_groups")
    if not isinstance(pseudo_groups, dict):
        return
    for group_name, group_data in pseudo_groups.items():
        if isinstance(group_data, dict) and "include" in group_data:
            raise ValueError(
                f"{source}: pseudo group '{group_name}' must not use include; "
                "put include on a final group and route pseudo fields with path."
            )


def _assert_no_nested_final_fields(raw: dict, source: str) -> None:
    for group_name, group_data in _workflow_group_items(raw):
        for field_path, field_data in _walk_field_items(group_data.get("fields")):
            if len(field_path) > 1:
                dotted_path = ".".join((group_name, *field_path))
                raise ValueError(
                    f"{source}: nested final fields are not supported by the "
                    f"harness runtime route parser: {dotted_path}"
                )
            if isinstance(field_data.get("fields"), dict):
                dotted_path = ".".join((group_name, *field_path))
                raise ValueError(
                    f"{source}: nested final fields are not supported by the "
                    f"harness runtime route parser: {dotted_path}"
                )


def _normalize_source_yaml(raw: dict, source: str) -> dict:
    _assert_required_v1_source_metadata(raw, source)
    _assert_source_top_level_shape(raw, source)
    workflow = typing.cast(dict, raw["workflow"])
    _assert_custom_steps_shape(workflow, source)
    _assert_source_group_shapes(raw, source)
    defs = raw.get("_defs")
    if defs is None:
        defs = {}
    else:
        defs = _ensure_mapping(defs, "_defs")
        for name in defs:
            _compose_def_fields(defs, str(name), ())
        _assert_def_field_shapes(defs, source)

    normalized = copy.deepcopy(raw)
    _assert_no_pseudo_group_include(normalized, source)
    for group_name, group_data in list(_workflow_group_items(normalized)):
        normalized[group_name] = _compose_group_fields(group_name, group_data, defs)
    _assert_source_group_shapes(normalized, source)
    _assert_no_nested_final_fields(normalized, source)
    return normalized


def _validated_source_yaml(raw: dict, source: str) -> dict:
    _assert_no_legacy_harness_metadata(raw, source)
    normalized = _normalize_source_yaml(raw, source)
    _assert_no_field_level_workflow_step(normalized, source)
    _assert_str_json_prompts_are_encoded_strings(normalized, source)
    _assert_pseudo_groups_are_routable(normalized, source)
    _assert_workflow_group_field_limit(normalized, source)
    _requires_custom_workflow_metadata(normalized, source)
    _assert_routed_raw_fields_name_output_keys(normalized, source)
    return normalized


def source_yaml_field_names(doc: typing.Any, source: str = "<yaml>") -> set[str]:
    if not isinstance(doc, dict):
        return set()
    normalized = _validated_source_yaml(doc, source)
    _prepare_extraction_yaml_fallback(normalized, source)
    names: set[str] = set()
    for group_name, group_data in _workflow_group_items(normalized):
        fields = group_data.get("fields")
        if isinstance(fields, dict):
            names.update(str(field_name) for field_name in fields)
    return names


def _assert_no_legacy_harness_metadata(raw: dict, source: str) -> None:
    if "domain" in raw:
        raise ValueError(
            f"{source}: harness templates do not support retired `domain:` YAML. "
            "Use `workflow.custom_steps` plus `workflow_step:` metadata for "
            "new harness-authored YAML."
        )
    for group_name, group_data in _workflow_group_items(raw):
        if "slot" in group_data:
            raise ValueError(
                f"{source}: workflow group '{group_name}' uses retired `slot:` "
                "metadata. Harness templates require top-level "
                "`workflow.custom_steps` and per-group `workflow_step:` metadata."
            )
    pseudo_groups = raw.get("_pseudo_groups")
    if isinstance(pseudo_groups, dict):
        for group_name, group_data in pseudo_groups.items():
            if isinstance(group_data, dict) and "slot" in group_data:
                raise ValueError(
                    f"{source}: pseudo group '{group_name}' uses retired `slot:` "
                    "metadata. Harness templates require `workflow_step:` on "
                    "direct workflow groups or pseudo groups."
                )


def _walk_field_items(
    fields: typing.Any,
    prefix: tuple[str, ...] = (),
) -> typing.Iterator[tuple[tuple[str, ...], dict]]:
    if not isinstance(fields, dict):
        return
    for field_name, field_data in fields.items():
        if not isinstance(field_data, dict):
            continue
        path = (*prefix, str(field_name))
        yield path, field_data
        nested_fields = field_data.get("fields")
        if isinstance(nested_fields, dict):
            yield from _walk_field_items(nested_fields, path)


def _assert_no_field_level_workflow_step(raw: dict, source: str) -> None:
    for group_name, group_data in _workflow_group_items(raw):
        for field_path, field_data in _walk_field_items(group_data.get("fields")):
            if "workflow_step" in field_data:
                dotted_path = ".".join((group_name, *field_path))
                raise ValueError(
                    f"{source}: field '{dotted_path}' uses field-level "
                    "`workflow_step`. Put `workflow_step:` on a direct workflow "
                    "group, or use `_pseudo_groups` with `path` routes for "
                    "split/recombine."
                )

    pseudo_groups = raw.get("_pseudo_groups")
    if not isinstance(pseudo_groups, dict):
        return
    for group_name, group_data in pseudo_groups.items():
        if not isinstance(group_data, dict):
            continue
        for field_path, field_data in _walk_field_items(group_data.get("fields")):
            if "workflow_step" in field_data:
                dotted_path = ".".join((str(group_name), *field_path))
                raise ValueError(
                    f"{source}: pseudo field '{dotted_path}' uses field-level "
                    "`workflow_step`. Put `workflow_step:` on the pseudo group."
                )


def _prompt_text_for_validation(prompt: typing.Any) -> str:
    if not isinstance(prompt, dict):
        return ""
    parts: list[str] = []
    for key in ("description", "format", "instructions"):
        value = prompt.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return "\n".join(parts).lower()


def _assert_str_json_prompts_are_encoded_strings(raw: dict, source: str) -> None:
    encoded_markers = (
        "json array string",
        "json object string",
        "json-encoded string",
        "json encoded string",
        "encoded as a string",
        "encode the json",
        "string containing json",
    )
    json_markers = ("json array", "json object")

    def check_field(group_name: str, field_path: tuple[str, ...], field_data: dict) -> None:
        prompt = field_data.get("prompt")
        if not isinstance(prompt, dict):
            return
        if str(prompt.get("type", "")).lower() != "str":
            return
        prompt_text = _prompt_text_for_validation(prompt)
        if not any(marker in prompt_text for marker in json_markers):
            return
        if any(marker in prompt_text for marker in encoded_markers):
            return
        dotted_path = ".".join((group_name, *field_path))
        raise ValueError(
            f"{source}: field '{dotted_path}' has type: str but asks for a "
            "native JSON array/object. Ask for a JSON-encoded string, or change "
            "the field type if the runtime should receive a structured value."
        )

    for group_name, group_data in _workflow_group_items(raw):
        for field_path, field_data in _walk_field_items(group_data.get("fields")):
            check_field(group_name, field_path, field_data)

    pseudo_groups = raw.get("_pseudo_groups")
    if not isinstance(pseudo_groups, dict):
        return
    for group_name, group_data in pseudo_groups.items():
        if not isinstance(group_data, dict):
            continue
        for field_path, field_data in _walk_field_items(group_data.get("fields")):
            check_field(str(group_name), field_path, field_data)


def _json_pointer_segments(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must start with '/': {pointer}")
    if pointer == "/":
        return []
    return [
        segment.replace("~1", "/").replace("~0", "~")
        for segment in pointer[1:].split("/")
    ]


def _resolve_final_field(groups: dict, pointer: str, source: str) -> dict:
    try:
        segments = _json_pointer_segments(pointer)
    except ValueError as exc:
        raise ValueError(f"{source}: invalid pseudo-group path [{pointer}]") from exc
    if len(segments) != 2:
        raise ValueError(
            f"{source}: pseudo-group path [{pointer}] must target one flat final field"
        )

    group_name = segments[0]
    group = groups.get(group_name)
    if not isinstance(group, dict):
        raise ValueError(f"{source}: pseudo-group path [{pointer}] targets unknown group")

    fields = group.get("fields")
    field_name = segments[1]
    if not isinstance(fields, dict) or field_name not in fields:
        raise ValueError(f"{source}: pseudo-group path [{pointer}] targets unknown field")
    field_data: typing.Any = fields[field_name]

    if not isinstance(field_data, dict):
        raise ValueError(f"{source}: pseudo-group path [{pointer}] must target a field mapping")
    return field_data


def _collect_final_leaf_paths(groups: dict) -> set[str]:
    leaf_paths: set[str] = set()

    def _walk(group_name: str, fields: typing.Any, prefix: tuple[str, ...] = ()) -> None:
        if not isinstance(fields, dict):
            return
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue
            path = (*prefix, str(field_name))
            nested_fields = field_data.get("fields")
            if isinstance(nested_fields, dict) and nested_fields:
                _walk(group_name, nested_fields, path)
            else:
                leaf_paths.add(_json_pointer((group_name, *path)))

    for group_name, group_data in groups.items():
        if isinstance(group_data, dict):
            _walk(str(group_name), group_data.get("fields"))

    return leaf_paths


def _collect_final_leaf_paths_for_routes(
    groups: dict,
    *,
    document_root_groups: typing.Set[str],
) -> set[str]:
    leaf_paths: set[str] = set()

    def _walk(group_name: str, fields: typing.Any, prefix: tuple[str, ...] = ()) -> None:
        if not isinstance(fields, dict):
            return
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue
            path = (*prefix, str(field_name))
            nested_fields = field_data.get("fields")
            if isinstance(nested_fields, dict) and nested_fields:
                _walk(group_name, nested_fields, path)
            elif group_name in document_root_groups:
                leaf_paths.add(_json_pointer(path))
            else:
                leaf_paths.add(_json_pointer((group_name, *path)))

    for group_name, group_data in groups.items():
        if isinstance(group_data, dict):
            _walk(str(group_name), group_data.get("fields"))

    return leaf_paths


def _assert_pseudo_groups_are_routable(raw: dict, source: str) -> None:
    pseudo_groups = raw.get("_pseudo_groups")
    if pseudo_groups is None:
        return
    if not isinstance(pseudo_groups, dict) or not pseudo_groups:
        raise ValueError(f"{source}: `_pseudo_groups` must be a non-empty mapping")

    final_groups = {name: data for name, data in _workflow_group_items(raw)}
    routed_paths: set[str] = set()
    routed_final_groups: set[str] = set()

    for pseudo_name, pseudo_group in pseudo_groups.items():
        if not isinstance(pseudo_group, dict):
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must be a mapping")
        if not isinstance(pseudo_group.get("workflow_step"), str):
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must declare workflow_step")
        fields = pseudo_group.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must declare non-empty fields")
        for output_key, field_data in fields.items():
            if not isinstance(field_data, dict):
                raise ValueError(
                    f"{source}: pseudo field '{pseudo_name}.{output_key}' must be a mapping"
                )
            if _CUSTOM_WORKFLOW_FIELD_METADATA_KEY in field_data:
                raise ValueError(
                    f"{source}: pseudo field '{pseudo_name}.{output_key}' must use "
                    "the pseudo field key as the workflow output key, not "
                    "`workflow_output_key`."
                )
            final_path = field_data.get("path")
            if not isinstance(final_path, str):
                raise ValueError(
                    f"{source}: pseudo field '{pseudo_name}.{output_key}' must declare path"
                )
            if final_path in routed_paths:
                raise ValueError(f"{source}: duplicate pseudo-group route to [{final_path}]")
            routed_paths.add(final_path)
            try:
                segments = _json_pointer_segments(final_path)
            except ValueError as exc:
                raise ValueError(f"{source}: invalid pseudo-group path [{final_path}]") from exc
            if segments:
                routed_final_groups.add(segments[0])
            _resolve_final_field(final_groups, final_path, source)

    for group_name in routed_final_groups:
        group = final_groups.get(group_name)
        if isinstance(group, dict) and "workflow_step" in group:
            raise ValueError(
                f"{source}: final group '{group_name}' is routed by `_pseudo_groups` "
                "and also declares direct `workflow_step:` metadata. Use one "
                "routing model for that final group."
            )


def _assert_workflow_group_field_limit(raw: dict, source: str) -> None:
    counts: dict[str, int] = {}

    for group_name, group_data in _workflow_group_items(raw):
        if "workflow_step" not in group_data:
            continue
        fields = group_data.get("fields")
        if isinstance(fields, dict):
            counts[group_name] = len(fields)

    pseudo_groups = raw.get("_pseudo_groups")
    if isinstance(pseudo_groups, dict):
        for group_name, group_data in pseudo_groups.items():
            if not isinstance(group_data, dict):
                continue
            fields = group_data.get("fields")
            if isinstance(fields, dict):
                counts[str(group_name)] = len(fields)

    for group_name, field_count in sorted(counts.items()):
        if field_count > _CUSTOM_WORKFLOW_GROUP_FIELD_LIMIT:
            raise ValueError(
                f"{source}: workflow group '{group_name}' has {field_count} "
                f"fields; custom workflow groups support "
                f"{_CUSTOM_WORKFLOW_GROUP_FIELD_LIMIT} fields or fewer."
            )


def _requires_custom_workflow_metadata(raw: dict, source: str) -> None:
    if _raw_uses_custom_workflow_metadata(raw):
        return
    raise ValueError(
        f"{source}: harness workflow YAML must declare top-level "
        "`workflow.custom_steps` and assign each workflow group with "
        "`workflow_step:`. Add v1 workflow metadata before using the harness "
        "compiler."
    )


def _assert_routed_raw_fields_name_output_keys(raw: dict, source: str) -> None:
    for group_name, group_data in _workflow_group_items(raw):
        if "workflow_step" not in group_data:
            continue
        fields = group_data.get("fields")
        if not isinstance(fields, dict):
            continue
        for field_path, field_data in _walk_field_items(fields):
            field_name = ".".join(field_path)
            if isinstance(field_data, dict) and "workflow_output_key" not in field_data:
                raise ValueError(
                    f"{source}: routed field {group_name}.{field_name} must declare "
                    "`workflow_output_key`. Harness-authored YAML uses explicit "
                    "custom output keys so every final field has a route."
                )


def _assert_prepared_workflow_groups_are_routed(prepared: typing.Any, source: str) -> None:
    workflow_groups = getattr(prepared, "workflow_groups", None)
    if not isinstance(workflow_groups, dict):
        return
    workflow_group_metadata = getattr(prepared, "workflow_group_metadata", None)
    if not isinstance(workflow_group_metadata, dict):
        workflow_group_metadata = {}

    for group_name, group_data in workflow_groups.items():
        if not isinstance(group_data, dict):
            continue
        fields = group_data.get("fields")
        if not isinstance(fields, dict) or not fields:
            continue
        metadata = workflow_group_metadata.get(group_name)
        if not isinstance(metadata, dict) or not metadata.get("workflow_step"):
            raise ValueError(
                f"{source}: final group '{group_name}' has fields but no "
                "`workflow_step:` metadata. Assign every real workflow group to "
                "a custom step, or route oversized final groups through "
                "`_pseudo_groups`."
            )


def _json_pointer(segments: typing.Iterable[str]) -> str:
    encoded = []
    for segment in segments:
        encoded.append(str(segment).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(encoded)


def _custom_workflow_output_map(level: str) -> str:
    output_map = _CUSTOM_WORKFLOW_OUTPUT_MAPS.get(level)
    if not output_map:
        raise ValueError(f"invalid custom workflow level [{level}]")
    return output_map


def _custom_workflow_readback_path(level: str, step_name: str, output_key: str) -> str:
    output_map = _custom_workflow_output_map(level)
    if level == "document":
        return f"/{output_map}/{step_name}/{output_key}"
    return f"/chunks/*/{output_map}/{step_name}/{output_key}"


def _strip_field_metadata(obj: typing.Any) -> typing.Any:
    if isinstance(obj, dict):
        return {
            key: _strip_field_metadata(value)
            for key, value in obj.items()
            if key not in {_CUSTOM_WORKFLOW_FIELD_METADATA_KEY, "workflow_step"}
        }
    if isinstance(obj, list):
        return [_strip_field_metadata(value) for value in obj]
    return copy.deepcopy(obj)


def _strip_group_metadata(group: dict) -> dict:
    stripped: dict = {}
    for key, value in group.items():
        if key in _GROUP_METADATA_KEYS:
            continue
        if key == "fields":
            stripped[key] = _strip_field_metadata(value)
        else:
            stripped[key] = copy.deepcopy(value)
    return stripped


def _field_type(field: dict) -> str:
    prompt = field.get("prompt")
    if isinstance(prompt, dict) and isinstance(prompt.get("type"), str):
        return prompt["type"]
    return "unknown"


def _workflow_field_name(prefix: tuple[str, ...], field_name: str) -> str:
    return ".".join((*prefix, field_name))


def _collect_fallback_custom_routes(
    *,
    fields: dict,
    group_name: str,
    document_root: bool,
    step_name: str,
    steps_by_name: dict,
    prefix: tuple[str, ...] = (),
) -> tuple[list[dict], list[dict], dict[str, str]]:
    routes: list[dict] = []
    leaves: list[dict] = []
    field_paths: dict[str, str] = {}

    for field_name, field_data in fields.items():
        if not isinstance(field_data, dict):
            continue
        output_key = field_data.get(_CUSTOM_WORKFLOW_FIELD_METADATA_KEY)
        if output_key is not None:
            step = steps_by_name.get(step_name)
            if step is None:
                raise ValueError(f"unknown custom step [{step_name}]")
            if not isinstance(output_key, str):
                raise ValueError(
                    f"workflow_output_key for [{group_name}.{field_name}] must be a string"
                )
            workflow_field = _workflow_field_name(prefix, str(field_name))
            final_path = (
                _json_pointer((*prefix, str(field_name)))
                if document_root
                else _json_pointer((group_name, *prefix, str(field_name)))
            )
            level = step["level"]
            route = {
                "workflow_group": group_name,
                "workflow_field": workflow_field,
                "final_path": final_path,
                "step_name": step_name,
                "level": level,
                "output_map": _custom_workflow_output_map(level),
                "output_key": output_key,
                "readback_path": _custom_workflow_readback_path(level, step_name, output_key),
            }
            leaf = {
                "final_path": final_path,
                "workflow_group": group_name,
                "workflow_field": workflow_field,
                "step_name": step_name,
                "level": level,
                "output_key": output_key,
                "field_type": _field_type(field_data),
                "is_repeated": False,
                "repetition_scope": "none",
            }
            routes.append(route)
            leaves.append(leaf)
            field_paths[workflow_field] = final_path

        nested_fields = field_data.get("fields")
        if isinstance(nested_fields, dict):
            nested_routes, nested_leaves, nested_paths = _collect_fallback_custom_routes(
                fields=nested_fields,
                group_name=group_name,
                document_root=document_root,
                step_name=step_name,
                steps_by_name=steps_by_name,
                prefix=(*prefix, str(field_name)),
            )
            routes.extend(nested_routes)
            leaves.extend(nested_leaves)
            field_paths.update(nested_paths)

    return routes, leaves, field_paths


def _collect_fallback_pseudo_group_routes(
    *,
    pseudo_groups: dict,
    final_groups: dict,
    steps_by_name: dict,
    source: str,
) -> tuple[dict, dict, list[dict], list[dict], dict[str, dict[str, str]]]:
    workflow_groups: dict[str, dict] = {}
    workflow_group_metadata: dict[str, dict] = {}
    routes: list[dict] = []
    leaves: list[dict] = []
    workflow_field_paths: dict[str, dict[str, str]] = {}

    for pseudo_name, pseudo_group in pseudo_groups.items():
        if not isinstance(pseudo_group, dict):
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must be a mapping")
        step_name = pseudo_group.get("workflow_step")
        if not isinstance(step_name, str):
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must declare workflow_step")
        step = steps_by_name.get(step_name)
        if step is None:
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' references unknown workflow_step [{step_name}]")
        fields = pseudo_group.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"{source}: pseudo group '{pseudo_name}' must declare non-empty fields")

        workflow_group = {
            key: copy.deepcopy(value)
            for key, value in pseudo_group.items()
            if key not in {"workflow_step", "fields"}
        }
        workflow_group["fields"] = {}
        group_paths: dict[str, str] = {}

        for output_key, field_data in fields.items():
            if not isinstance(field_data, dict):
                raise ValueError(f"{source}: pseudo field '{pseudo_name}.{output_key}' must be a mapping")
            final_path = field_data.get("path")
            if not isinstance(final_path, str):
                raise ValueError(f"{source}: pseudo field '{pseudo_name}.{output_key}' must declare path")

            final_field = _resolve_final_field(final_groups, final_path, source)
            field_body = _strip_field_metadata(final_field)
            overrides = {
                key: copy.deepcopy(value)
                for key, value in field_data.items()
                if key not in {"path", _CUSTOM_WORKFLOW_FIELD_METADATA_KEY, "workflow_step"}
            }
            if overrides:
                field_body.update(_strip_field_metadata(overrides))
            workflow_group["fields"][str(output_key)] = field_body

            level = step["level"]
            route = {
                "workflow_group": str(pseudo_name),
                "workflow_field": str(output_key),
                "final_path": final_path,
                "step_name": step_name,
                "level": level,
                "output_map": _custom_workflow_output_map(level),
                "output_key": str(output_key),
                "readback_path": _custom_workflow_readback_path(level, step_name, str(output_key)),
            }
            leaf = {
                "final_path": final_path,
                "workflow_group": str(pseudo_name),
                "workflow_field": str(output_key),
                "step_name": step_name,
                "level": level,
                "output_key": str(output_key),
                "field_type": _field_type(final_field),
                "is_repeated": False,
                "repetition_scope": "none",
            }
            routes.append(route)
            leaves.append(leaf)
            group_paths[str(output_key)] = final_path

        workflow_groups[str(pseudo_name)] = workflow_group
        workflow_group_metadata[str(pseudo_name)] = {"workflow_step": step_name}
        workflow_field_paths[str(pseudo_name)] = group_paths

    return workflow_groups, workflow_group_metadata, routes, leaves, workflow_field_paths


def _custom_workflow_schema_hash(metadata: dict) -> str:
    steps: list[dict] = []
    for step in metadata.get("custom_steps", []):
        normalized_step = {
            "name": step["name"],
            "level": step["level"],
            "kind": step["kind"],
        }
        keys = sorted(step.get("required_template_keys", []))
        if keys:
            normalized_step["required_template_keys"] = keys
        steps.append(normalized_step)

    routes = [
        {
            "final_path": route["final_path"],
            "workflow_group": route["workflow_group"],
            "workflow_field": route["workflow_field"],
            "step_name": route["step_name"],
            "level": route["level"],
            "output_map": route["output_map"],
            "output_key": route["output_key"],
            "readback_path": route["readback_path"],
        }
        for route in metadata.get("output_routes", [])
    ]
    leaves = [
        {
            "final_path": leaf["final_path"],
            "workflow_group": leaf["workflow_group"],
            "workflow_field": leaf["workflow_field"],
            "step_name": leaf["step_name"],
            "level": leaf["level"],
            "output_key": leaf["output_key"],
            "field_type": leaf["field_type"],
            "is_repeated": leaf["is_repeated"],
            "repetition_scope": leaf["repetition_scope"],
        }
        for leaf in metadata.get("leaf_fields", [])
    ]

    steps.sort(key=lambda step: step["name"])
    routes.sort(key=_custom_route_identity)
    leaves.sort(key=_custom_leaf_identity)

    payload: dict[str, typing.Any] = {
        "metadata_version": metadata.get("metadata_version", 1)
    }
    if steps:
        payload["custom_steps"] = steps
    if routes:
        payload["output_routes"] = routes
    if leaves:
        payload["leaf_fields"] = leaves

    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _custom_route_identity(route: dict) -> str:
    return "\x00".join(
        [
            route["final_path"],
            route["workflow_group"],
            route["workflow_field"],
            route["step_name"],
            route["output_key"],
        ]
    )


def _custom_leaf_identity(leaf: dict) -> str:
    return "\x00".join(
        [
            leaf["final_path"],
            leaf["workflow_group"],
            leaf["workflow_field"],
            leaf["step_name"],
            leaf["output_key"],
        ]
    )


def _validate_agent_chain(raw_chain: list, workflow_groups: set[str]) -> None:
    first_stage = raw_chain[0]
    if not isinstance(first_stage, dict) or set(first_stage.keys()) != {"parallel"}:
        raise ValueError("workflow.agent_chain must start with a parallel stage")

    has_save = False
    serial_start_index = 1
    covered_groups: set[str] = set()
    for stage_index, raw_stage in enumerate(raw_chain):
        if isinstance(raw_stage, str):
            _validate_agent_chain_task(
                raw_stage,
                f"workflow.agent_chain[{stage_index}]",
            )
            if raw_stage in _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS:
                has_save = True
            continue

        if not isinstance(raw_stage, dict) or set(raw_stage.keys()) != {"parallel"}:
            raise ValueError(
                "workflow.agent_chain stages must be task strings or {parallel: [...]}"
            )
        if stage_index != 0:
            raise ValueError(
                "workflow.agent_chain parallel stages after the first stage are not supported"
            )

        raw_branches = raw_stage["parallel"]
        if not isinstance(raw_branches, list) or not raw_branches:
            raise ValueError("workflow.agent_chain parallel stage must have branches")

        branch_terminal_saves: list[bool] = []
        branch_suffixes: list[str] = []

        for branch_index, raw_branch in enumerate(raw_branches):
            path = f"workflow.agent_chain[{stage_index}].parallel[{branch_index}]"
            if not isinstance(raw_branch, dict):
                raise ValueError(f"{path} must be a mapping")
            if set(raw_branch.keys()) != {"group", "chain"}:
                raise ValueError(f"{path} must contain only group and chain")

            group = raw_branch["group"]
            if not isinstance(group, str) or not group:
                raise ValueError(f"{path}.group must be a non-empty string")
            if group not in workflow_groups:
                raise ValueError(f"{path}.group [{group}] is not a workflow group")
            covered_groups.add(group)

            chain = raw_branch["chain"]
            if not isinstance(chain, list) or not chain:
                raise ValueError(f"{path}.chain must be a non-empty list")
            parsed_chain = [
                _validate_agent_chain_task(task, f"{path}.chain")
                for task in chain
            ]
            if any(
                task in _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS
                for task in parsed_chain[:-1]
            ):
                raise ValueError(f"{path}.chain save task must be last")
            suffixes = {_agent_chain_task_suffix(task) for task in parsed_chain}
            if len(suffixes) != 1:
                raise ValueError(f"{path}.chain must use one processing suffix")
            branch_suffixes.append(suffixes.pop())
            branch_terminal_saves.append(
                parsed_chain[-1] in _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS
            )

        terminal_save = _agent_chain_following_save_task(raw_chain, stage_index)
        if any(branch_terminal_saves):
            has_save = True
            serial_start_index = stage_index + 1
            if terminal_save is not None:
                raise ValueError(
                    "workflow.agent_chain parallel branch save tasks cannot be "
                    "combined with a following top-level save task"
                )
            if not all(branch_terminal_saves):
                raise ValueError(
                    "workflow.agent_chain parallel branches must either all end in "
                    "save tasks or all use the following top-level save task"
                )
        elif terminal_save is None:
            raise ValueError(
                "workflow.agent_chain parallel branches must end in a save task or "
                "be followed by one top-level save task"
            )
        else:
            serial_start_index = stage_index + 2
            terminal_suffix = _agent_chain_task_suffix(terminal_save)
            for suffix in branch_suffixes:
                if suffix != terminal_suffix:
                    raise ValueError(
                        "workflow.agent_chain parallel branch processing suffix "
                        "must match following save task"
                    )

    if not has_save:
        raise ValueError("workflow.agent_chain must include a save task")
    _validate_agent_chain_serial_tasks(raw_chain, serial_start_index)
    _validate_agent_chain_group_coverage(
        raw_chain,
        workflow_groups,
        covered_groups,
        serial_start_index,
    )


def _validate_agent_chain_serial_tasks(
    raw_chain: list[typing.Any],
    start_index: int,
) -> None:
    stage_index = start_index
    while stage_index < len(raw_chain):
        path = f"workflow.agent_chain[{stage_index}]"
        task = _validate_agent_chain_task(raw_chain[stage_index], path)
        if task in _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS:
            raise ValueError(
                f"{path} top-level save task [{task}] must follow a matching "
                "top-level agent task"
            )

        expected_save = f"save_{_agent_chain_task_suffix(task)}"
        next_index = stage_index + 1
        if next_index >= len(raw_chain):
            raise ValueError(
                f"{path} top-level agent task [{task}] must be followed by "
                f"matching save task [{expected_save}]"
            )

        next_path = f"workflow.agent_chain[{next_index}]"
        next_task = _validate_agent_chain_task(raw_chain[next_index], next_path)
        if next_task != expected_save:
            raise ValueError(
                f"{path} top-level agent task [{task}] must be followed by "
                f"matching save task [{expected_save}]"
            )
        stage_index += 2


def _validate_agent_chain_group_coverage(
    raw_chain: list[typing.Any],
    workflow_groups: set[str],
    branch_covered_groups: set[str],
    serial_start_index: int,
) -> None:
    covered_groups = set(branch_covered_groups)
    stage_index = serial_start_index
    while stage_index < len(raw_chain):
        raw_stage = raw_chain[stage_index]
        if (
            isinstance(raw_stage, str)
            and raw_stage in _CUSTOM_WORKFLOW_AGENT_CHAIN_AGENT_TASKS
        ):
            suffix = _agent_chain_task_suffix(raw_stage)
            if suffix in workflow_groups:
                covered_groups.add(suffix)
            stage_index += 2
            continue
        stage_index += 1

    missing_groups = sorted(workflow_groups - covered_groups)
    if missing_groups:
        raise ValueError(
            "workflow.agent_chain does not cover workflow groups "
            f"[{', '.join(missing_groups)}]"
        )


def _validate_agent_chain_task(task: typing.Any, path: str) -> str:
    if not isinstance(task, str) or not task:
        raise ValueError(f"{path} task must be a non-empty string")
    if task not in _CUSTOM_WORKFLOW_AGENT_CHAIN_SUPPORTED_TASKS:
        raise ValueError(f"{path} contains unsupported task [{task}]")
    return task


def _agent_chain_following_save_task(
    raw_chain: list[typing.Any],
    stage_index: int,
) -> typing.Optional[str]:
    next_index = stage_index + 1
    if next_index >= len(raw_chain):
        return None
    raw_next = raw_chain[next_index]
    if (
        isinstance(raw_next, str)
        and raw_next in _CUSTOM_WORKFLOW_AGENT_CHAIN_SAVE_TASKS
    ):
        return raw_next
    return None


def _agent_chain_task_suffix(task: str) -> str:
    return task.rsplit("_", 1)[-1]


def _agent_chain_group_roles(raw_chain: typing.Any) -> dict[str, str]:
    roles: dict[str, str] = {}
    if not isinstance(raw_chain, list):
        return roles
    for raw_stage in raw_chain:
        if not isinstance(raw_stage, dict) or not isinstance(
            raw_stage.get("parallel"),
            list,
        ):
            continue
        for raw_branch in raw_stage["parallel"]:
            if not isinstance(raw_branch, dict):
                continue
            group = raw_branch.get("group")
            chain = raw_branch.get("chain")
            if not isinstance(group, str) or not isinstance(chain, list):
                continue
            suffixes = {
                _agent_chain_task_suffix(task)
                for task in chain
                if isinstance(task, str)
                and task in _CUSTOM_WORKFLOW_AGENT_CHAIN_SUPPORTED_TASKS
            }
            if len(suffixes) == 1:
                roles[group] = suffixes.pop()
    return roles


def _is_document_root_statement_group(group_data: dict) -> bool:
    return isinstance(group_data.get("final_value_aliases"), dict) or isinstance(
        group_data.get("fill_rules"),
        list,
    )


def _prepare_extraction_yaml_fallback(raw: dict, source: str) -> _PreparedExtractionYaml:
    workflow = raw.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError("workflow.custom_steps is required for harness workflow YAML")
    custom_steps = workflow.get("custom_steps")
    if not isinstance(custom_steps, list) or not custom_steps:
        raise ValueError("workflow.custom_steps must be a non-empty list")

    normalized_steps: list[dict] = []
    steps_by_name: dict[str, dict] = {}
    for index, step in enumerate(custom_steps):
        if not isinstance(step, dict):
            raise ValueError(f"workflow.custom_steps[{index}] must be a mapping")
        name = step.get("name")
        level = step.get("level")
        kind = step.get("kind")
        if not isinstance(name, str) or not name:
            raise ValueError(f"workflow.custom_steps[{index}].name must be a string")
        if not isinstance(level, str) or level not in _CUSTOM_WORKFLOW_OUTPUT_MAPS:
            raise ValueError(f"workflow.custom_steps[{index}].level is invalid")
        if kind not in {"instruct", "keys", "summary"}:
            raise ValueError(f"workflow.custom_steps[{index}].kind is invalid")
        normalized_step = {"name": name, "level": level, "kind": kind}
        if "config" in step:
            normalized_step["config"] = copy.deepcopy(step["config"])
        if step.get("required_template_keys"):
            normalized_step["required_template_keys"] = copy.deepcopy(step["required_template_keys"])
        normalized_steps.append(normalized_step)
        steps_by_name[name] = normalized_step

    top_level_metadata = {
        key: copy.deepcopy(raw[key])
        for key in _TOP_LEVEL_METADATA_KEYS
        if key in raw
    }
    agent_chain = workflow.get("agent_chain")
    workflow_group_roles = _agent_chain_group_roles(agent_chain)
    document_root_groups: set[str] = set()
    groups: dict[str, dict] = {}
    final_group_metadata: dict[str, dict] = {}
    workflow_group_metadata: dict[str, dict] = {}
    workflow_field_paths: dict[str, dict] = {}
    workflow_groups: dict[str, dict] = {}
    routes: list[dict] = []
    leaves: list[dict] = []

    for group_name, group_data in _workflow_group_items(raw):
        fields = group_data.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"final group '{group_name}' must declare non-empty fields")

        groups[group_name] = _strip_group_metadata(group_data)
        metadata = {
            key: copy.deepcopy(value)
            for key, value in group_data.items()
            if key in _FINAL_GROUP_METADATA_KEYS
        }
        if metadata:
            final_group_metadata[group_name] = metadata

        step_name = group_data.get("workflow_step")
        if step_name is None:
            continue
        if not isinstance(step_name, str):
            raise ValueError(f"workflow group '{group_name}' must declare workflow_step as a string")
        if step_name not in steps_by_name:
            raise ValueError(f"workflow group '{group_name}' references unknown workflow_step [{step_name}]")

        workflow_groups[group_name] = _strip_group_metadata(group_data)
        workflow_group_metadata[group_name] = {"workflow_step": step_name}
        document_root = (
            workflow_group_roles.get(group_name) == "statement"
            and _is_document_root_statement_group(group_data)
        )
        if document_root:
            document_root_groups.add(group_name)
        group_routes, group_leaves, group_paths = _collect_fallback_custom_routes(
            fields=fields,
            group_name=group_name,
            document_root=document_root,
            step_name=step_name,
            steps_by_name=steps_by_name,
        )
        routes.extend(group_routes)
        leaves.extend(group_leaves)
        workflow_field_paths[group_name] = group_paths

    pseudo_groups = raw.get("_pseudo_groups")
    if isinstance(pseudo_groups, dict):
        (
            pseudo_workflow_groups,
            pseudo_workflow_metadata,
            pseudo_routes,
            pseudo_leaves,
            pseudo_paths,
        ) = _collect_fallback_pseudo_group_routes(
            pseudo_groups=pseudo_groups,
            final_groups={name: data for name, data in _workflow_group_items(raw)},
            steps_by_name=steps_by_name,
            source=source,
        )
        workflow_groups.update(pseudo_workflow_groups)
        workflow_group_metadata.update(pseudo_workflow_metadata)
        routes.extend(pseudo_routes)
        leaves.extend(pseudo_leaves)
        workflow_field_paths.update(pseudo_paths)

    if not routes or not leaves:
        raise ValueError(
            "custom workflow steps require direct routed fields with "
            "workflow_output_key or `_pseudo_groups` fields with path"
        )
    routed_final_paths = {
        route["final_path"]
        for route in routes
        if isinstance(route.get("final_path"), str)
    }
    missing_final_paths = sorted(
        _collect_final_leaf_paths_for_routes(
            groups,
            document_root_groups=document_root_groups,
        )
        - routed_final_paths
    )
    if missing_final_paths:
        missing = ", ".join(missing_final_paths[:5])
        suffix = "" if len(missing_final_paths) <= 5 else ", ..."
        missing_groups = sorted(
            {
                path.strip("/").split("/", 1)[0]
                for path in missing_final_paths
                if path.strip("/")
            }
        )
        if len(missing_groups) == 1:
            group_detail = f"final group '{missing_groups[0]}' has fields"
        elif missing_groups:
            group_detail = "final groups " + ", ".join(
                f"'{group}'" for group in missing_groups[:5]
            )
            if len(missing_groups) > 5:
                group_detail += ", ..."
            group_detail += " have fields"
        else:
            group_detail = "final fields"
        raise ValueError(
            f"{source}: {group_detail} not routed. Use direct group "
            f"`workflow_step:` plus field `workflow_output_key`, or "
            f"`_pseudo_groups` fields with `path`: {missing}{suffix}"
        )

    field_counts: dict[str, int] = {}
    for route in routes:
        step_name = route["step_name"]
        field_counts[step_name] = field_counts.get(step_name, 0) + 1

    workflow_metadata: dict[str, typing.Any] = {
        "metadata_version": 1,
        "custom_steps": normalized_steps,
        "output_routes": routes,
        "leaf_fields": leaves,
    }
    if workflow.get("section_strategy"):
        workflow_metadata["section_strategy"] = workflow["section_strategy"]
    if workflow.get("template"):
        workflow_metadata["template"] = copy.deepcopy(workflow["template"])
    if field_counts:
        workflow_metadata["field_counts"] = field_counts
    if agent_chain is not None:
        if not isinstance(agent_chain, list) or not agent_chain:
            raise ValueError("workflow.agent_chain must be a non-empty list")
        _validate_agent_chain(agent_chain, {route["workflow_group"] for route in routes})
        workflow_metadata["agent_chain"] = copy.deepcopy(agent_chain)
    workflow_metadata["schema_hash"] = _custom_workflow_schema_hash(workflow_metadata)

    persisted_workflow_extract = copy.deepcopy(workflow_groups)
    persisted_workflow_extract["workflow"] = copy.deepcopy(workflow_metadata)
    persisted_workflow_extract["_groundx_persisted_extract"] = copy.deepcopy(raw)

    return _PreparedExtractionYaml(
        groups=groups,
        workflow_groups=copy.deepcopy(workflow_groups),
        pseudo_groups=copy.deepcopy(pseudo_groups) if isinstance(pseudo_groups, dict) else {},
        workflow_field_paths=workflow_field_paths,
        persisted_workflow_extract=persisted_workflow_extract,
        top_level_metadata=top_level_metadata,
        final_group_metadata=final_group_metadata,
        workflow_group_metadata=workflow_group_metadata,
    )


def _normalize_prepared_document_root_routes(prepared: typing.Any, raw: dict) -> typing.Any:
    workflow = raw.get("workflow")
    agent_chain = workflow.get("agent_chain") if isinstance(workflow, dict) else None
    roles = _agent_chain_group_roles(agent_chain)
    document_root_groups = {
        group_name
        for group_name, group_data in _workflow_group_items(raw)
        if roles.get(group_name) == "statement"
        and _is_document_root_statement_group(group_data)
    }
    if not document_root_groups:
        return prepared

    def normalize_pointer(pointer: typing.Any, group_name: str) -> typing.Any:
        if not isinstance(pointer, str):
            return pointer
        prefix = f"/{group_name}/"
        if pointer.startswith(prefix):
            return "/" + pointer[len(prefix):]
        return pointer

    persisted = getattr(prepared, "persisted_workflow_extract", None)
    if isinstance(persisted, dict):
        metadata = persisted.get("workflow")
        if isinstance(metadata, dict):
            for route in metadata.get("output_routes", []) or []:
                if not isinstance(route, dict):
                    continue
                group_name = route.get("workflow_group")
                if group_name in document_root_groups:
                    route["final_path"] = normalize_pointer(route.get("final_path"), group_name)
            for leaf in metadata.get("leaf_fields", []) or []:
                if not isinstance(leaf, dict):
                    continue
                group_name = leaf.get("workflow_group")
                if group_name in document_root_groups:
                    leaf["final_path"] = normalize_pointer(leaf.get("final_path"), group_name)
            metadata["schema_hash"] = _custom_workflow_schema_hash(metadata)

    workflow_field_paths = getattr(prepared, "workflow_field_paths", None)
    if isinstance(workflow_field_paths, dict):
        for group_name in document_root_groups:
            paths = workflow_field_paths.get(group_name)
            if not isinstance(paths, dict):
                continue
            for field_name, pointer in list(paths.items()):
                paths[field_name] = normalize_pointer(pointer, group_name)

    return prepared


def _prepare_schema(raw_yaml: str, source: str) -> typing.Any:
    raw = _safe_load_yaml(raw_yaml, source) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: top-level YAML must be a mapping of groups")
    raw = _validated_source_yaml(raw, source)

    workflow_metadata = raw.get("workflow")
    if (
        _sdk_prepare_extraction_yaml is None
        or "_pseudo_groups" in raw
        or (
            isinstance(workflow_metadata, dict)
            and "section_strategy" in workflow_metadata
        )
    ):
        return _prepare_extraction_yaml_fallback(raw, source)

    prepared_raw_yaml = yaml.safe_dump(raw, sort_keys=False)
    prepared = _sdk_prepare_extraction_yaml(
        prepared_raw_yaml,
        top_level_metadata_keys=_TOP_LEVEL_METADATA_KEYS,
        final_group_metadata_keys=_FINAL_GROUP_METADATA_KEYS,
        workflow_group_metadata_keys=_WORKFLOW_GROUP_METADATA_KEYS,
    )
    return _normalize_prepared_document_root_routes(prepared, raw)


def _read_and_prepare_schema(yaml_path: str) -> tuple[str, typing.Any]:
    with open(yaml_path, encoding="utf-8") as f:
        raw_yaml = f.read()
    prepared = _prepare_schema(raw_yaml, yaml_path)
    if not isinstance(getattr(prepared, "workflow_groups", None), dict):
        raise ValueError(f"{yaml_path}: prepared workflow groups must be a mapping")
    if not isinstance(getattr(prepared, "groups", None), dict):
        raise ValueError(f"{yaml_path}: prepared final groups must be a mapping")
    _assert_prepared_workflow_groups_are_routed(prepared, yaml_path)
    return raw_yaml, prepared


def _requires_persisted_workflow_extract(raw_yaml: str, source: str) -> bool:
    raw = _safe_load_yaml(raw_yaml, source) or {}
    if not isinstance(raw, dict):
        return False

    if (
        any(key in raw for key in _TOP_LEVEL_METADATA_KEYS)
        or "_groundx_persisted_extract" in raw
        or "_pseudo_groups" in raw
        or "_defs" in raw
        or _contains_include(raw)
    ):
        return True

    for group_name, group_data in raw.items():
        if group_name in RESERVED_TOP_LEVEL_KEYS:
            continue
        if isinstance(group_data, dict) and any(
            key in group_data for key in _PERSISTED_EXTRACT_REQUIRED_GROUP_KEYS
        ):
            return True

    return False


def _persisted_workflow_extract(
    *,
    raw_yaml: str,
    source: str,
    prepared: typing.Any,
) -> dict:
    sdk_persisted = getattr(prepared, "persisted_workflow_extract", None)
    if sdk_persisted is not None:
        if not isinstance(sdk_persisted, dict):
            raise ValueError("prepared persisted workflow extract must be a mapping")
        persisted = copy.deepcopy(sdk_persisted)
        if (
            _requires_persisted_workflow_extract(raw_yaml, source)
            and "_groundx_persisted_extract" not in persisted
        ):
            raw = _safe_load_yaml(raw_yaml, source) or {}
            if not isinstance(raw, dict):
                raise ValueError(f"{source}: top-level YAML must be a mapping of groups")
            persisted["_groundx_persisted_extract"] = copy.deepcopy(raw)
        return persisted

    workflow_groups = getattr(prepared, "workflow_groups", None)
    if not isinstance(workflow_groups, dict):
        raise ValueError("prepared workflow groups must be a mapping")

    persisted = copy.deepcopy(workflow_groups)
    if _requires_persisted_workflow_extract(raw_yaml, source):
        raw = _safe_load_yaml(raw_yaml, source) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: top-level YAML must be a mapping of groups")
        persisted["_groundx_persisted_extract"] = copy.deepcopy(raw)
    return persisted


def _to_dict(obj: typing.Any) -> typing.Any:
    # by_alias=True preserves the wire-format key names (e.g. `engineID`,
    # `chunk-keys`, `all`). Pydantic v2 `model_dump` keeps None values;
    # the v1 `.dict()` fallback uses by_alias=True too but still drops
    # unset fields — workflow_steps_for_yaml compensates by passing them
    # explicitly.
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True)
    if hasattr(obj, "dict"):
        return obj.dict(by_alias=True)
    return obj


def _custom_workflow_metadata(prepared: typing.Any) -> typing.Optional[dict]:
    persisted = getattr(prepared, "persisted_workflow_extract", None)
    if not isinstance(persisted, dict):
        return None
    workflow = persisted.get("workflow")
    if not isinstance(workflow, dict):
        return None
    if not workflow.get("custom_steps"):
        return None
    return workflow


_REPEATED_CUSTOM_STEP_KINDS = _CUSTOM_WORKFLOW_REPEATED_STEP_KINDS


def _repeat_pointer_for_step(pointer: typing.Any, should_repeat: bool) -> typing.Any:
    if not should_repeat or not isinstance(pointer, str) or "*" in pointer:
        return pointer
    parts = [part for part in pointer.split("/")[1:] if part]
    if len(parts) < 2:
        return pointer
    return "/" + "/".join([*parts[:-1], "*", parts[-1]])


def _repetition_scope(pointer: typing.Any) -> str:
    # The live GroundX API only accepts the enum values "none", "field", or
    # "item" for workflow.leafFields[].repetitionScope; it rejects path-format
    # values like "/meters/*". A wildcard pointer is a repeated list-item leaf,
    # which maps to "item" (the API expands it back to /meters/* on storage).
    if not isinstance(pointer, str):
        return "none"
    return "item" if "*" in pointer.split("/") else "none"


def _normalized_custom_workflow_metadata(metadata: dict) -> dict:
    normalized = copy.deepcopy(metadata)
    repeated_steps = {
        step.get("name")
        for step in normalized.get("custom_steps", []) or []
        if isinstance(step, dict) and step.get("kind") in _REPEATED_CUSTOM_STEP_KINDS
    }

    for route in normalized.get("output_routes", []) or []:
        if not isinstance(route, dict):
            continue
        route["final_path"] = _repeat_pointer_for_step(
            route.get("final_path"),
            route.get("step_name") in repeated_steps,
        )

    for leaf in normalized.get("leaf_fields", []) or []:
        if not isinstance(leaf, dict):
            continue
        is_repeated = leaf.get("step_name") in repeated_steps
        leaf["final_path"] = _repeat_pointer_for_step(leaf.get("final_path"), is_repeated)
        leaf["is_repeated"] = is_repeated
        leaf["repetition_scope"] = _repetition_scope(leaf.get("final_path")) if is_repeated else "none"

    return normalized


def _prompt_text(value: typing.Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _field_prompt(field: dict) -> dict:
    prompt = field.get("prompt")
    if isinstance(prompt, dict):
        return prompt
    return {}


def _field_description(field: dict) -> str:
    return _prompt_text(_field_prompt(field).get("description")) or "No description provided."


def _field_spec(output_key: str, field: dict) -> str:
    prompt = _field_prompt(field)
    identifiers = prompt.get("identifiers")
    if isinstance(identifiers, list):
        identifiers_text = ", ".join(str(item) for item in identifiers)
    else:
        identifiers_text = _prompt_text(identifiers)

    lines = [
        f"## {output_key}",
        "",
        f"Field: {output_key}",
        f"Description: {_prompt_text(prompt.get('description'))}",
        f"Type: {_prompt_text(prompt.get('type'))}",
    ]
    if prompt.get("format") is not None:
        lines.append(f"Format: {_prompt_text(prompt.get('format'))}")
    if identifiers_text:
        lines.append(f"Example Identifiers: {identifiers_text}")
    instructions = _prompt_text(prompt.get("instructions"))
    if instructions:
        lines.extend(["Special Instructions:", instructions])
    return "\n".join(lines)


def _field_description_bullet(output_key: str, field: dict) -> str:
    return f"- **{output_key}** - {_field_description(field)}"


def _group_instructions(workflow_group: dict) -> str:
    prompt = workflow_group.get("prompt")
    if isinstance(prompt, dict):
        return _prompt_text(prompt.get("instructions"))
    return ""


def _response_contract(kind: str) -> str:
    if kind == "instruct":
        return "Return one JSON object whose keys exactly match the output keys."
    return (
        "Return a JSON array of objects. Each object must use only the configured "
        "output keys."
    )


def _empty_response(kind: str) -> str:
    if kind == "instruct":
        return "{}"
    return "[]"


def _response_noun(kind: str) -> str:
    if kind == "instruct":
        return "JSON object"
    return "JSON array"


def _configured_output_key_list(output_keys: list[str]) -> str:
    return "\n".join(f"- `{key}`" for key in output_keys)


def _group_definition(group_name: str, instructions: str) -> str:
    if not instructions:
        return ""
    return f"# {group_name} Definition\n\n{instructions.strip()}"


def _custom_extract_request_prompt(
    *,
    step_name: str,
    step_kind: str,
    workflow_group: str,
    field_specs: str,
    group_definition: str,
    output_keys: list[str],
) -> str:
    group_section = ""
    if group_definition:
        group_section = f"\n{group_definition.strip()}\n"

    return """
# Request

I am going to provide you with content from a document. I want you to analyze this content, extract the relevant information for the configured workflow group, and return it as a {response_noun}.

# Extraction Guidelines

Below are the relevant fields that I want you to extract from the content, including the key to use in your JSON response, the format of the JSON value, and examples or instructions for how the information may be identified. These identifiers and examples are guidance, not an exhaustive list.

- If page images are provided with extracted text excerpts, use the images as context for the extracted text. Focus your extraction on the provided document content.
- If extracted text cuts off important surrounding context, use the page image context to repair that issue.
- Extract only values supported by the document content. Do not infer values that are not supported by the source.
- Follow field-specific null, enum, condition, and formatting instructions. If a field has no specific null rule and you cannot identify it with confidence, exclude that key from the response.

{group_section}
# Field Descriptions

{field_specs}

# Output Contract

- Custom workflow step: `{step_name}`
- Workflow group: `{workflow_group}`
- Step kind: `{step_kind}`
- {response_contract}
- Use only these output keys:
{output_keys}

# Final Notes

- Use the value in `Field` as the key in your JSON response for the given field.
- If you cannot identify a field with confidence, exclude it unless that field's instructions explicitly require `null`.
- If you cannot find any fields with confidence, return an empty {response_noun} like this: `{empty_response}`.
- Do not add commentary, markdown fences, or explanation text.
- Only return the {response_noun} in your response.
""".format(
        empty_response=_empty_response(step_kind),
        field_specs=field_specs.strip(),
        group_section=group_section,
        output_keys=_configured_output_key_list(output_keys),
        response_contract=_response_contract(step_kind),
        response_noun=_response_noun(step_kind),
        step_kind=step_kind,
        step_name=step_name,
        workflow_group=workflow_group,
    )


def _custom_extract_task_prompt(
    *,
    step_name: str,
    step_kind: str,
    workflow_group: str,
    field_descriptions: str,
) -> str:
    return """
# Identity

You are a structured-data extraction assistant that extracts information from document content and returns the information in JSON format.

# Process

Your process for extracting structured information from document content is as follows:

1. You are provided with document content as text, page images, or a combination of text and page images.
  - If you are provided with text, you are provided with extracted text excerpts from the document.
  - If you are provided with page images, you are provided with images for the same document scope.
  - If you are provided with both, use the page images as context for the extracted text.
2. Analyze page images only to provide context for the extracted text excerpts.
  - If text excerpts cut off important surrounding context, use the page images to repair the cutoff.
  - Do not use image-only guesses when the value is not supported by the document content.
3. Carefully analyze the provided document content for the following configured fields:
{field_descriptions}
4. For each value you find, follow the formatting and condition instructions for that field.
  - Use the configured `Field` value as the JSON key.
  - If a value is absent or low confidence, follow the field-specific instruction. If there is no field-specific null rule, exclude that key.
  - Do not invent placeholder values such as "Not Provided", "N/A", or similar filler.
5. Construct the response for custom workflow step `{step_name}` in workflow group `{workflow_group}`.
  - {response_contract}
  - Return only keys from the configured output-key contract.
6. Return the JSON response, and only the JSON response.
  - It is critical that you respond with only JSON because I will parse your response as JSON and extraneous commentary or text will break the parser.

# Examples

<document_text>
This excerpt does not contain any configured field values.
</document_text>

<assistant_response>
{empty_response}
</assistant_response>

<document_content>
The source contains a configured value for one of the requested fields.
</document_content>

<assistant_response>
{positive_example}
</assistant_response>
""".format(
        empty_response=_empty_response(step_kind),
        field_descriptions=field_descriptions.strip(),
        positive_example=(
            '{"<configured_output_key>": "<source-supported value>"}'
            if step_kind == "instruct"
            else '[{"<configured_output_key>": "<source-supported value>"}]'
        ),
        response_contract=_response_contract(step_kind),
        step_name=step_name,
        workflow_group=workflow_group,
    )


def _routes_by_step(metadata: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for route in metadata.get("output_routes", []) or []:
        if not isinstance(route, dict):
            continue
        step_name = route.get("step_name")
        if isinstance(step_name, str):
            grouped.setdefault(step_name, []).append(route)
    return grouped


def _step_by_name(metadata: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for step in metadata.get("custom_steps", []) or []:
        if isinstance(step, dict) and isinstance(step.get("name"), str):
            out[step["name"]] = step
    return out


def _workflow_group_for_step(
    *,
    step_name: str,
    routes: list[dict],
    workflow_groups: dict,
) -> tuple[str, dict]:
    group_names = sorted(
        {
            route.get("workflow_group")
            for route in routes
            if isinstance(route.get("workflow_group"), str)
        }
    )
    if len(group_names) != 1:
        raise ValueError(
            f"custom workflow step [{step_name}] must route exactly one workflow "
            f"group; got {group_names}. Use one workflow group per custom step."
        )
    group_name = group_names[0]
    group = workflow_groups.get(group_name)
    if not isinstance(group, dict):
        raise ValueError(
            f"custom workflow step [{step_name}] references unknown workflow group "
            f"[{group_name}]"
        )
    return group_name, group


def _workflow_field_for_route(workflow_group: dict, route: dict) -> dict:
    fields = workflow_group.get("fields")
    field_name = route.get("workflow_field")
    if not isinstance(fields, dict) or not isinstance(field_name, str):
        return {}
    field = fields.get(field_name)
    if isinstance(field, dict):
        return field
    return {}


def _render_custom_step_prompt(
    *,
    step: dict,
    group_name: str,
    workflow_group: dict,
    routes: list[dict],
) -> dict:
    kind = str(step.get("kind") or "")
    step_name = str(step.get("name") or "")
    output_keys = [str(route.get("output_key")) for route in routes if route.get("output_key")]
    field_specs = []
    field_bullets = []
    for route in routes:
        output_key = str(route.get("output_key") or route.get("workflow_field") or "")
        field = _workflow_field_for_route(workflow_group, route)
        field_specs.append(_field_spec(output_key, field))
        field_bullets.append(_field_description_bullet(output_key, field))

    instructions = _group_instructions(workflow_group)
    request = _custom_extract_request_prompt(
        step_name=step_name,
        step_kind=kind,
        workflow_group=group_name,
        field_specs="\n\n".join(field_specs),
        group_definition=_group_definition(group_name, instructions),
        output_keys=output_keys,
    )
    task = _custom_extract_task_prompt(
        step_name=step_name,
        step_kind=kind,
        workflow_group=group_name,
        field_descriptions="\n".join(field_bullets),
    )

    return {"request": request, "task": task}


def _merge_prompt_config(config: typing.Any, prompt: dict) -> dict:
    if isinstance(config, dict):
        merged = copy.deepcopy(config)
    else:
        merged = {}

    for molecule_key in _CUSTOM_WORKFLOW_PROMPT_MOLECULE_KEYS:
        molecule_config = merged.get(molecule_key)
        if isinstance(molecule_config, dict):
            molecule_config = copy.deepcopy(molecule_config)
        else:
            molecule_config = {}
        prompt_config = molecule_config.get("prompt")
        if isinstance(prompt_config, dict):
            prompt_config = copy.deepcopy(prompt_config)
        else:
            prompt_config = {}
        prompt_config.setdefault("request", prompt["request"])
        prompt_config.setdefault("task", prompt["task"])
        includes = molecule_config.get("includes")
        if isinstance(includes, dict):
            includes = copy.deepcopy(includes)
        else:
            includes = {}
        includes.setdefault("pageImages", True)
        molecule_config["includes"] = includes
        molecule_config["prompt"] = prompt_config
        merged[molecule_key] = molecule_config
    return merged


def _with_rendered_custom_step_prompts(metadata: dict, prepared: typing.Any) -> dict:
    workflow_groups = getattr(prepared, "workflow_groups", None)
    if not isinstance(workflow_groups, dict):
        raise ValueError("prepared workflow groups must be a mapping")

    normalized = copy.deepcopy(metadata)
    routes_by_step = _routes_by_step(normalized)
    steps_by_name = _step_by_name(normalized)
    for step_name, routes in routes_by_step.items():
        step = steps_by_name.get(step_name)
        if step is None:
            continue
        group_name, workflow_group = _workflow_group_for_step(
            step_name=step_name,
            routes=routes,
            workflow_groups=workflow_groups,
        )
        prompt = _render_custom_step_prompt(
            step=step,
            group_name=group_name,
            workflow_group=workflow_group,
            routes=routes,
        )
        step["config"] = _merge_prompt_config(step.get("config"), prompt)
    return normalized


def _with_normalized_workflow_metadata(persisted_extract: dict, metadata: dict) -> dict:
    persisted = copy.deepcopy(persisted_extract)
    persisted["workflow"] = copy.deepcopy(metadata)
    authored = persisted.get("_groundx_persisted_extract")
    if isinstance(authored, dict):
        authored["workflow"] = copy.deepcopy(metadata)
    return persisted


def _empty_workflow_steps() -> dict:
    if WorkflowSteps is None:
        return {key: None for key in _EMPTY_WORKFLOW_STEP_KEYS}
    steps = _to_dict(WorkflowSteps(**{attr: None for attr in _ALL_STAGE_ATTRS}))
    for key in _EMPTY_WORKFLOW_STEP_KEYS:
        steps.setdefault(key, None)
    for key in _DISABLED_DEFAULT_EXTRACTION_STEPS:
        steps[key] = None
    return steps


def _custom_step_body(step: dict) -> dict:
    body = {
        "name": step["name"],
        "level": step["level"],
        "kind": step["kind"],
    }
    if "config" in step:
        body["config"] = copy.deepcopy(step["config"])
    required_keys = step.get("required_template_keys")
    if required_keys:
        body["requiredTemplateKeys"] = copy.deepcopy(required_keys)
    return body


def _custom_route_body(route: dict) -> dict:
    return {
        "workflowGroup": route["workflow_group"],
        "workflowField": route["workflow_field"],
        "finalPath": route["final_path"],
        "stepName": route["step_name"],
        "level": route["level"],
        "outputMap": route["output_map"],
        "outputKey": route["output_key"],
        "readbackPath": route["readback_path"],
    }


def _custom_leaf_body(leaf: dict) -> dict:
    return {
        "finalPath": leaf["final_path"],
        "workflowGroup": leaf["workflow_group"],
        "workflowField": leaf["workflow_field"],
        "stepName": leaf["step_name"],
        "level": leaf["level"],
        "outputKey": leaf["output_key"],
        "fieldType": leaf["field_type"],
        "isRepeated": leaf["is_repeated"],
        "repetitionScope": leaf["repetition_scope"],
    }


def _custom_workflow_body_fields(metadata: dict) -> dict:
    body: dict = {
        "customSteps": [_custom_step_body(step) for step in metadata.get("custom_steps", [])],
        "outputRoutes": [_custom_route_body(route) for route in metadata.get("output_routes", [])],
        "leafFields": [_custom_leaf_body(leaf) for leaf in metadata.get("leaf_fields", [])],
    }
    template = metadata.get("template")
    if template:
        body["template"] = copy.deepcopy(template)
    return body


def workflow_sdk_kwargs(workflow: dict) -> dict:
    kwargs = {
        "name": workflow["name"],
        "chunk_strategy": workflow.get("chunk_strategy"),
        "section_strategy": workflow.get("section_strategy"),
        "extract": workflow.get("extract"),
        "steps": workflow.get("steps"),
    }
    optional_fields = {
        "template": "template",
        "custom_steps": "customSteps",
        "output_routes": "outputRoutes",
        "leaf_fields": "leafFields",
    }
    for sdk_key, workflow_key in optional_fields.items():
        if workflow_key in workflow:
            kwargs[sdk_key] = workflow.get(workflow_key)
    return kwargs


def _metadata_from_prepared(
    yaml_path: str,
    raw_yaml: str,
    prepared: typing.Any,
) -> dict:
    return {
        "schema_version": "extraction_workflow_metadata_v1",
        "source_yaml": {
            "path": os.path.abspath(yaml_path),
            "sha256": hashlib.sha256(raw_yaml.encode("utf-8")).hexdigest(),
        },
        "workflow_field_paths": copy.deepcopy(prepared.workflow_field_paths),
        "prepared_final_groups": copy.deepcopy(prepared.groups),
        "top_level_metadata": copy.deepcopy(prepared.top_level_metadata),
        "final_group_metadata": copy.deepcopy(prepared.final_group_metadata),
        "workflow_group_metadata": copy.deepcopy(prepared.workflow_group_metadata),
    }


def build_workflow_artifacts(
    yaml_path: str,
    name: typing.Optional[str] = None,
) -> tuple[dict, dict]:
    """Compile a YAML schema into workflow JSON plus reassembly metadata.

    Exposed for in-process callers (e.g. run_extraction.py) so they can
    skip the subprocess + file round-trip that the CLI entry point uses.
    """
    yaml_dir = os.path.dirname(os.path.abspath(yaml_path)) or "."
    yaml_basename = os.path.splitext(os.path.basename(yaml_path))[0]
    resolved_name = name or yaml_basename

    raw_yaml, prepared = _read_and_prepare_schema(yaml_path)
    persisted_extract = _persisted_workflow_extract(
        raw_yaml=raw_yaml,
        source=yaml_path,
        prepared=prepared,
    )
    custom_metadata = _custom_workflow_metadata(prepared)
    if custom_metadata is not None:
        custom_metadata = _normalized_custom_workflow_metadata(custom_metadata)
        custom_metadata = _with_rendered_custom_step_prompts(custom_metadata, prepared)
        # Recompute schema_hash over the normalized leaves so it matches what
        # the SDK recomputes at update_prompts() time.  The hash was originally
        # stored before normalization (pre-wildcard final_path, repetition_scope
        # still "none") and would be stale for any repeated group.
        custom_metadata["schema_hash"] = _custom_workflow_schema_hash(custom_metadata)
        persisted_extract = _with_normalized_workflow_metadata(persisted_extract, custom_metadata)
        workflow = {
            "name": resolved_name,
            "chunk_strategy": "element",
            "section_strategy": custom_metadata.get("section_strategy"),
            "extract": _to_dict(persisted_extract),
            "steps": _empty_workflow_steps(),
            **_custom_workflow_body_fields(custom_metadata),
        }
        return workflow, _metadata_from_prepared(yaml_path, raw_yaml, prepared)

    raise ValueError(
        f"{yaml_path}: harness workflow YAML must compile through "
        "`workflow.custom_steps` and `workflow_step:` metadata. Add v1 workflow "
        "metadata before using the harness compiler."
    )


def build_workflow(yaml_path: str, name: typing.Optional[str] = None) -> dict:
    """Compile a YAML schema into a workflow JSON dict."""
    workflow, _ = build_workflow_artifacts(yaml_path, name=name)
    return workflow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml_path")
    parser.add_argument(
        "--name",
        default=None,
        help="Workflow name. Defaults to the YAML basename.",
    )
    args = parser.parse_args()

    workflow = build_workflow(args.yaml_path, name=args.name)
    sys.stdout.write(json.dumps(workflow, indent=2, default=str))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
