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
    "unique_attrs",
}

_TOP_LEVEL_METADATA_KEYS = {"extraction_policy_version"}
_WORKFLOW_GROUP_METADATA_KEYS = {"workflow_step"}
_FINAL_GROUP_METADATA_KEYS = _GROUP_METADATA_KEYS - _WORKFLOW_GROUP_METADATA_KEYS
_PERSISTED_EXTRACT_REQUIRED_GROUP_KEYS = _GROUP_METADATA_KEYS
_CUSTOM_WORKFLOW_FIELD_METADATA_KEY = "workflow_output_key"
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
    if len(segments) < 2:
        raise ValueError(f"{source}: pseudo-group path [{pointer}] must target a final field")

    group_name = segments[0]
    group = groups.get(group_name)
    if not isinstance(group, dict):
        raise ValueError(f"{source}: pseudo-group path [{pointer}] targets unknown group")

    fields = group.get("fields")
    field_data: typing.Any = None
    for segment in (s for s in segments[1:] if s != "*"):
        if not isinstance(fields, dict) or segment not in fields:
            raise ValueError(f"{source}: pseudo-group path [{pointer}] targets unknown field")
        field_data = fields[segment]
        fields = field_data.get("fields") if isinstance(field_data, dict) else None

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
        for field_name, field_data in fields.items():
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
            final_path = _json_pointer((group_name, *prefix, str(field_name)))
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
        group_routes, group_leaves, group_paths = _collect_fallback_custom_routes(
            fields=fields,
            group_name=group_name,
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
    missing_final_paths = sorted(_collect_final_leaf_paths(groups) - routed_final_paths)
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
    if workflow.get("template"):
        workflow_metadata["template"] = copy.deepcopy(workflow["template"])
    if field_counts:
        workflow_metadata["field_counts"] = field_counts
    agent_chain = workflow.get("agent_chain")
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


def _prepare_schema(raw_yaml: str, source: str) -> typing.Any:
    raw = _safe_load_yaml(raw_yaml, source) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: top-level YAML must be a mapping of groups")
    _assert_no_legacy_harness_metadata(raw, source)
    _assert_no_field_level_workflow_step(raw, source)
    _assert_pseudo_groups_are_routable(raw, source)
    _requires_custom_workflow_metadata(raw, source)
    _assert_routed_raw_fields_name_output_keys(raw, source)

    if _sdk_prepare_extraction_yaml is None or "_pseudo_groups" in raw:
        return _prepare_extraction_yaml_fallback(raw, source)

    return _sdk_prepare_extraction_yaml(
        raw_yaml,
        top_level_metadata_keys=_TOP_LEVEL_METADATA_KEYS,
        final_group_metadata_keys=_FINAL_GROUP_METADATA_KEYS,
        workflow_group_metadata_keys=_WORKFLOW_GROUP_METADATA_KEYS,
    )


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
    if not isinstance(pointer, str):
        return "none"
    parts = [part for part in pointer.split("/")[1:] if part]
    if "*" not in parts:
        return "none"
    return "/" + "/".join(parts[: parts.index("*") + 1])


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
    return _to_dict(WorkflowSteps(**{attr: None for attr in _ALL_STAGE_ATTRS}))


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
        persisted_extract = _with_normalized_workflow_metadata(persisted_extract, custom_metadata)
        workflow = {
            "name": resolved_name,
            "chunk_strategy": "element",
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
