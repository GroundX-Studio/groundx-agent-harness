#!/usr/bin/env python3
"""Compile a YAML extraction schema into a GroundX workflow JSON.

Usage:
    python compile_workflow.py <prompt.yaml> [--name NAME] > workflow.json

Outputs the workflow JSON to stdout. Does NOT call any GroundX API —
this is a pure offline transformation. The output is the exact body
shape you POST to `/v1/workflow` (or pass to `gx.workflows.create()`,
or to the `workflow_create` MCP tool from the groundx-api skill).

Domain-agnostic workflow group→slot mapping
-------------------------------------------
The compiler carries no hardcoded final group names. Top-level real YAML groups
define the final data object. Optional `_pseudo_groups` define workflow-only
execution groups for splitting a large final group or combining small sibling
final groups. The SDK prepares both surfaces before compilation.

Each prepared workflow group resolves its workflow slot by precedence:

  1. SDK-resolved workflow metadata such as explicit/inherited `slot:`, then
  2. a top-level `domain:` whose profile (templates/domains/<domain>.yaml)
     supplies the workflow-group→slot map, then
  3. a hard error if neither is present.

Slots must be on the proven menu (SLOT_MENU): `chunk-instruct` (singleton
per-document object), `chunk-keys` and `chunk-summary` (repeating record
arrays). Multiple workflow groups may share a slot; the compiler renders one
combined prompt for that slot. Reserved authoring keys and metadata are consumed
locally and never reach the workflow JSON. Compile/run/deploy paths also emit
`extraction_workflow_metadata_v1.json`, which carries the route map and final
schema for reassembly.

Reads .env for EXTRACT_MODEL_* (engine config). No real GROUNDX_API_KEY is
needed because no API calls are made; a placeholder is acceptable.

For the actual API calls (workflow create, attach to bucket, ingest,
poll, retrieve extract), use the groundx-api skill — that is the
source of truth for those operations.
"""

import argparse
import copy
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import typing

import dotenv
import yaml

# Resolve .env from the user's cwd, not the script's __file__ tree.
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from groundx import (
    GroundX,
    WorkflowEngine,
    WorkflowPrompt,
    WorkflowPromptGroup,
    WorkflowStep,
    WorkflowStepConfig,
    WorkflowSteps,
)
from groundx.extract import Logger, PromptManager, Source

try:
    from groundx.extract import prepare_extraction_yaml as _sdk_prepare_extraction_yaml
except ImportError:
    _sdk_prepare_extraction_yaml = None


# --- Proven slot menu + reserved keys -------------------------------------
#
# The platform exposes a grid of pipeline-stage slots (level × kind). Only the
# three chunk-level slots below are PROVEN for structured extraction (live +
# via xray_to_extract.py). `field` is the output field the step writes to —
# decoupled from the slot name — which xray_to_extract.py reads back:
#   chunk-instruct → field sect-sum  → X-Ray sectionSummary → singleton object
#   chunk-keys     → field (none)    → X-Ray chunkKeywords   → repeating array
#   chunk-summary  → field chunk-sum → X-Ray chunkSummary    → repeating array
# Expanding this menu requires the slot spike (see openspec extraction-runner-e2e).
SLOT_MENU: typing.Dict[str, typing.Dict[str, typing.Any]] = {
    "chunk-instruct": {"stage": "chunk_instruct", "field": "sect-sum", "kind": "singleton"},
    "chunk-keys": {"stage": "chunk_keys", "field": None, "kind": "repeating"},
    "chunk-summary": {"stage": "chunk_summary", "field": "chunk-sum", "kind": "repeating"},
}

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
RESERVED_TOP_LEVEL_KEYS = {"domain", "_defs", "_pseudo_groups"}

# Per-group keys consumed locally and stripped before the YAML reaches the SDK
# PromptManager: the slot selector plus the client-side business-logic metadata
# (applied post-extraction by templates/business_logic.py, not on the platform).
# Keeping them out of the filtered YAML ensures they never become extract fields.
_GROUP_METADATA_KEYS = {
    "slot",
    "unique_attrs",
    "match_attrs",
    "conflict_attrs",
    "passthrough",
    "pipeline",
}

_TOP_LEVEL_METADATA_KEYS = {"domain"}
_WORKFLOW_GROUP_METADATA_KEYS = {"slot"}
_FINAL_GROUP_METADATA_KEYS = _GROUP_METADATA_KEYS - _WORKFLOW_GROUP_METADATA_KEYS

# Domain profiles live next to this script.
DOMAINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domains")


@dataclasses.dataclass
class _PreparedWorkflowSchema:
    groups: dict
    workflow_groups: dict
    pseudo_groups: dict
    workflow_field_paths: dict
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


def _contains_include(obj: typing.Any) -> bool:
    if isinstance(obj, dict):
        if "include" in obj:
            return True
        return any(_contains_include(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_include(v) for v in obj)
    return False


def _identity_route_map(groups: dict) -> dict:
    route_map: dict = {}
    for group_name, group in groups.items():
        if not isinstance(group, dict):
            continue
        fields = group.get("fields")
        if not isinstance(fields, dict):
            continue
        route_map[group_name] = {
            str(field_name): f"/{group_name}/{field_name}" for field_name in fields.keys()
        }
    return route_map


def _prepare_legacy_schema(raw: dict) -> _PreparedWorkflowSchema:
    top_level_metadata = {
        key: copy.deepcopy(raw[key]) for key in _TOP_LEVEL_METADATA_KEYS if key in raw
    }
    groups: dict = {}
    final_group_metadata: dict = {}
    workflow_group_metadata: dict = {}
    for group_name, value in raw.items():
        if group_name in RESERVED_TOP_LEVEL_KEYS:
            continue
        if isinstance(value, dict):
            final_meta = {
                key: copy.deepcopy(value[key])
                for key in _FINAL_GROUP_METADATA_KEYS
                if key in value
            }
            workflow_meta = {
                key: copy.deepcopy(value[key])
                for key in _WORKFLOW_GROUP_METADATA_KEYS
                if key in value
            }
            if final_meta:
                final_group_metadata[group_name] = final_meta
            if workflow_meta:
                workflow_group_metadata[group_name] = workflow_meta
            groups[group_name] = {
                key: copy.deepcopy(item)
                for key, item in value.items()
                if key not in _GROUP_METADATA_KEYS
            }
        else:
            groups[group_name] = copy.deepcopy(value)

    return _PreparedWorkflowSchema(
        groups=groups,
        workflow_groups=copy.deepcopy(groups),
        pseudo_groups={},
        workflow_field_paths=_identity_route_map(groups),
        top_level_metadata=top_level_metadata,
        final_group_metadata=final_group_metadata,
        workflow_group_metadata=workflow_group_metadata,
    )


def _prepare_schema(raw_yaml: str, source: str) -> typing.Any:
    if _sdk_prepare_extraction_yaml is not None:
        return _sdk_prepare_extraction_yaml(
            raw_yaml,
            top_level_metadata_keys=_TOP_LEVEL_METADATA_KEYS,
            final_group_metadata_keys=_FINAL_GROUP_METADATA_KEYS,
            workflow_group_metadata_keys=_WORKFLOW_GROUP_METADATA_KEYS,
        )

    raw = _safe_load_yaml(raw_yaml, source) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: top-level YAML must be a mapping of groups")
    if "_pseudo_groups" in raw or "_defs" in raw or _contains_include(raw):
        raise RuntimeError(
            "YAML features `_pseudo_groups`, `_defs`, and `include` use syntax "
            "that requires groundx[extract] with prepare_extraction_yaml support. "
            "Upgrade the GroundX Python SDK to the pseudo-group release or remove "
            "those features for legacy YAML compilation."
        )
    return _prepare_legacy_schema(raw)


def _read_and_prepare_schema(yaml_path: str) -> tuple[str, typing.Any]:
    with open(yaml_path, encoding="utf-8") as f:
        raw_yaml = f.read()
    prepared = _prepare_schema(raw_yaml, yaml_path)
    if not isinstance(getattr(prepared, "workflow_groups", None), dict):
        raise ValueError(f"{yaml_path}: prepared workflow groups must be a mapping")
    if not isinstance(getattr(prepared, "groups", None), dict):
        raise ValueError(f"{yaml_path}: prepared final groups must be a mapping")
    return raw_yaml, prepared


# --- Generic prompt builders ----------------------------------------------
#
# Two builders keyed by slot kind, parameterized by group name. They carry no
# domain vocabulary: domain-specific guidance belongs in the YAML (per-field
# `instructions` and the group-level `prompt`/definition), not here.


def _singleton_request(field_specs: str) -> str:
    return f"""
# Request

Analyze the provided document content and return the extracted information
as a JSON object.

# Field Descriptions

{field_specs.strip()}

# Final Notes

- If you cannot identify a field with confidence, exclude it.
- If you cannot find any fields with confidence, return {{}}.
- Use the value in `Field` as the JSON key.
- Return only the JSON object.
"""


def _singleton_task(field_descriptions: str) -> str:
    return f"""
# Identity

You are a structured-data assistant. Extract information from documents and
return the information as a JSON object.

# Process

1. You analyze the provided text excerpts and any page images for context.
2. You look for the following fields:
{field_descriptions}
3. For each field found, follow the formatting instructions for that field.
4. Construct a JSON object using the `Field` value as each key.
5. Return only the JSON object — extraneous commentary will break the parser.
"""


def _repeating_request(group_name: str, field_specs: str, group_definition: str) -> str:
    return f"""
# Request

Analyze the provided document content and extract every individual record.

# Extraction Guidelines

{group_definition.strip()}

# Field Values

You must extract the following information for each record, if it can be
found.

{field_specs.strip()}

# Output shape

Return a single JSON object whose top-level key is `{group_name}` and whose
value is a JSON array of record objects. Each record object uses the
field `Field` value (above) as its keys.

Example shape (illustrative — field names are placeholders, use the
real `Field` values from "Field Values" above):

```json
{{
  "{group_name}": [
    {{"field_a": "value", "field_b": 123}},
    {{"field_a": "value", "field_b": 456}}
  ]
}}
```

If you cannot find any records in this content, return `{{"{group_name}": []}}`.

DO NOT return a raw JSON array at the top level. DO NOT invent records
that are not visible in the content provided. Only include records you
can read directly from the document text or page images.

# Final Notes

- Use the value in `Field` as the JSON key inside each record.
- Exclude fields you cannot identify with confidence.
- Return only the JSON object — no commentary, no code fences.
"""


def _repeating_task(group_name: str, field_descriptions: str) -> str:
    return f"""
# Identity

You are a structured-data assistant. Extract repeating records from documents
and return them as a JSON object with a `{group_name}` array.

# Process

1. Identify each individual record (line item, charge, transaction) that
   is visible in the provided document content. Do not invent records.
2. For each record, look for the following fields:
{field_descriptions}
3. Build one JSON object per record with the `Field` values as keys.
4. Wrap the array of record objects in a top-level `{{"{group_name}": [...]}}`
   object. Always use the `{group_name}` key — never return a raw array,
   never use a different wrapper name.
5. If no records are found, return `{{"{group_name}": []}}`.
6. Return only the resulting JSON object.
    """


# --- Optional external wrapper support ------------------------------------


def _load_wrapper_module(yaml_dir: str) -> typing.Any:
    """Load optional prompt wrappers from EXTRACT_WRAPPER_MODULE.

    `EXTRACT_WRAPPER_MODULE` may be a normal Python module path
    (`prompts.extract_statement`) or a file path relative to the YAML
    directory (`prompts/extract_statement.py`). Missing/empty means use the
    default inline wrappers below.
    """
    module_ref = os.environ.get("EXTRACT_WRAPPER_MODULE", "").strip()
    if not module_ref:
        return None

    if module_ref.endswith(".py") or os.path.sep in module_ref:
        module_path = module_ref
        if not os.path.isabs(module_path):
            module_path = os.path.join(yaml_dir, module_path)
        spec = importlib.util.spec_from_file_location("extract_prompt_wrappers", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load EXTRACT_WRAPPER_MODULE={module_ref}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return importlib.import_module(module_ref)


def _call_wrapper(
    module: typing.Any,
    names: tuple[str, ...],
    fallback: typing.Callable[..., str],
    *args: typing.Any,
) -> str:
    if module is not None:
        for name in names:
            fn = getattr(module, name, None)
            if callable(fn):
                return fn(*args)
    return fallback(*args)


def _wrapper_names(group_name: str, verb: str) -> tuple[str, ...]:
    """Per-group prompt-wrapper override names (back-compatible).

    For `statement`/`charges`/`meters` these reproduce the historical names
    (`prompt_statement_extract_request`, ...); for any other group they follow
    the same pattern keyed by the group name.
    """
    return (
        f"prompt_{group_name}_extract_{verb}",
        f"{group_name}_extract_{verb}",
        f"extract_{group_name}_{verb}",
    )


# --- Domain profiles + slot resolution ------------------------------------


def _load_domain_profile(domain: str) -> typing.Dict[str, str]:
    """Load a domain profile's group→slot map from templates/domains/<domain>.yaml."""
    path = os.path.join(DOMAINS_DIR, f"{domain}.yaml")
    if not os.path.isfile(path):
        available = sorted(
            f[:-5] for f in os.listdir(DOMAINS_DIR) if f.endswith(".yaml")
        ) if os.path.isdir(DOMAINS_DIR) else []
        raise ValueError(
            f"unknown domain '{domain}'. No profile at {path}. "
            f"Available domains: {available or '(none)'}. "
            f"Declare a known `domain:` or give each group an explicit `slot:`."
        )
    with open(path, encoding="utf-8") as f:
        profile = _safe_load_yaml(f.read(), path) or {}
    groups = profile.get("groups") or {}
    if not isinstance(groups, dict) or not groups:
        raise ValueError(f"domain profile {path} has no `groups:` map")
    return {str(g): str(s) for g, s in groups.items()}


def _resolve_group_slots(prepared: typing.Any) -> "dict[str, str]":
    """Resolve each workflow group's slot.

    Slot metadata already reflects SDK pseudo-group override/inheritance rules.
    Harness only interprets the resolved workflow metadata, falls back to a
    domain profile keyed by workflow group name, and validates the proven menu.
    """
    top_level_metadata = getattr(prepared, "top_level_metadata", {}) or {}
    workflow_group_metadata = getattr(prepared, "workflow_group_metadata", {}) or {}
    workflow_groups = getattr(prepared, "workflow_groups", {}) or {}
    domain = top_level_metadata.get("domain")
    profile: typing.Optional[typing.Dict[str, str]] = None

    group_names = list(workflow_groups.keys())
    if not group_names:
        raise ValueError("no workflow groups found in prepared YAML")

    resolved: dict[str, str] = {}
    for name in group_names:
        metadata = workflow_group_metadata.get(name) or {}
        slot = metadata.get("slot")
        if not slot and domain:
            if profile is None:
                profile = _load_domain_profile(str(domain))
            slot = profile.get(name)
        if not slot:
            raise ValueError(
                f"workflow group '{name}' has no slot. Declare a `slot:` on the "
                f"workflow group/final group "
                f"(one of {sorted(SLOT_MENU)}) or a top-level `domain:` whose "
                f"profile maps '{name}'."
            )
        if slot not in SLOT_MENU:
            raise ValueError(
                f"workflow group '{name}' declares slot '{slot}', which is not on the "
                f"proven slot menu {sorted(SLOT_MENU)}."
            )
        resolved[name] = slot
    return resolved


def _write_prepared_workflow_yaml(workflow_groups: dict, yaml_dir: str) -> str:
    """Write prepared workflow groups so PromptManager parses only execution groups."""
    fd, path = tempfile.mkstemp(dir=yaml_dir, prefix="_cf_", suffix=".yaml")
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(workflow_groups, f, sort_keys=False, allow_unicode=True)
    return path


# --- Compile helper -------------------------------------------------------


class _CompileManager(PromptManager):
    """PromptManager subclass used purely for offline YAML→JSON compilation."""

    def __init__(
        self,
        *,
        model_id: str,
        model_reasoning: typing.Optional[str],
        service: str,
        group_slots: typing.Dict[str, str],
        wrapper_module: typing.Any = None,
        **data: typing.Any,
    ) -> None:
        super().__init__(**data)
        self.model_id = model_id
        self.model_reasoning = model_reasoning
        self.service = service
        self.group_slots = group_slots
        self.wrapper_module = wrapper_module

    def _engine(self) -> WorkflowEngine:
        return WorkflowEngine(
            engine_id=self.model_id,
            reasoning_effort=self.model_reasoning,
            service=self.service,
        )

    def get_fields_for_workflow(self, *args: typing.Any, **kwargs: typing.Any) -> dict:
        # Defensive: never let a reserved key surface as an extract group.
        fields = super().get_fields_for_workflow(*args, **kwargs)
        return {k: v for k, v in fields.items() if k not in RESERVED_TOP_LEVEL_KEYS}

    def _combined_group_field_prompts(self, group_names: typing.Sequence[str]) -> str:
        if len(group_names) == 1:
            return self.group_field_prompts(group_names[0])
        blocks = []
        for group_name in group_names:
            blocks.append(
                f"# Workflow group: {group_name}\n\n"
                f"{self.group_field_prompts(group_name)}"
            )
        return "\n\n".join(blocks)

    def _combined_group_descriptions(self, group_names: typing.Sequence[str]) -> str:
        if len(group_names) == 1:
            return self.group_descriptions(group_names[0])
        blocks = []
        for group_name in group_names:
            blocks.append(
                f"- Workflow group `{group_name}`:\n"
                f"{self.group_descriptions(group_name)}"
            )
        return "\n".join(blocks)

    def _combined_group_definition(self, group_names: typing.Sequence[str]) -> str:
        blocks = []
        for group_name in group_names:
            try:
                definition = self.group_definition(group_name).strip()
            except Exception:
                definition = ""
            if definition:
                blocks.append(f"# Workflow group: {group_name}\n\n{definition}")
        return "\n\n".join(blocks)

    def _multi_repeating_request(
        self,
        group_names: typing.Sequence[str],
        field_specs: str,
        group_definition: str,
    ) -> str:
        group_list = ", ".join(f"`{name}`" for name in group_names)
        empty_shape = ", ".join(f'"{name}": []' for name in group_names)
        return f"""
# Request

Analyze the provided document content and extract every individual record for
these workflow groups: {group_list}.

# Extraction Guidelines

{group_definition.strip()}

# Field Values

You must extract the following information for each workflow group, if it can
be found.

{field_specs.strip()}

# Output shape

Return a single JSON object with one top-level array key for each workflow group:
{group_list}. Each record object uses the field `Field` value as its keys.

If you cannot find any records in this content, return `{{{empty_shape}}}`.
Do not invent records that are not visible in the document content.
Return only the JSON object.
"""

    def _multi_repeating_task(
        self,
        group_names: typing.Sequence[str],
        field_descriptions: str,
    ) -> str:
        group_list = ", ".join(f"`{name}`" for name in group_names)
        return f"""
# Identity

You are a structured-data assistant. Extract repeating records from documents
and return them as a JSON object with array keys for these workflow groups:
{group_list}.

# Process

1. Identify each individual record that is visible in the provided document
   content. Do not invent records.
2. For each workflow group, look for the following fields:
{field_descriptions}
3. Build one JSON object per visible record with the `Field` values as keys.
4. Wrap records under the appropriate workflow group key. Never return a raw
   array.
5. If no records are found for a workflow group, return an empty array for that
   group.
6. Return only the resulting JSON object.
"""

    def _step_config(
        self,
        group_names: typing.Sequence[str],
        slot_meta: dict,
    ) -> WorkflowStepConfig:
        primary_group = group_names[0]
        if slot_meta["kind"] == "singleton":
            field_specs = self._combined_group_field_prompts(group_names)
            field_descriptions = self._combined_group_descriptions(group_names)
            if len(group_names) == 1:
                request_prompt = _call_wrapper(
                    self.wrapper_module,
                    _wrapper_names(primary_group, "request"),
                    _singleton_request,
                    field_specs,
                )
                task_prompt = _call_wrapper(
                    self.wrapper_module,
                    _wrapper_names(primary_group, "task"),
                    _singleton_task,
                    field_descriptions,
                )
            else:
                request_prompt = _singleton_request(field_specs)
                task_prompt = _singleton_task(field_descriptions)
        else:  # repeating
            field_specs = self._combined_group_field_prompts(group_names)
            field_descriptions = self._combined_group_descriptions(group_names)
            group_definition = self._combined_group_definition(group_names)
            if len(group_names) == 1:
                request_prompt = _call_wrapper(
                    self.wrapper_module,
                    _wrapper_names(primary_group, "request"),
                    lambda fs, gd: _repeating_request(primary_group, fs, gd),
                    field_specs,
                    self.group_definition(primary_group),
                )
                task_prompt = _call_wrapper(
                    self.wrapper_module,
                    _wrapper_names(primary_group, "task"),
                    lambda fd: _repeating_task(primary_group, fd),
                    field_descriptions,
                )
            else:
                request_prompt = self._multi_repeating_request(
                    group_names, field_specs, group_definition
                )
                task_prompt = self._multi_repeating_task(group_names, field_descriptions)
        return WorkflowStepConfig(
            engine=self._engine(),
            field=slot_meta["field"],
            includes={"pageImages": True},
            prompt=WorkflowPromptGroup(
                request=WorkflowPrompt(prompt=request_prompt, role="user"),
                task=WorkflowPrompt(prompt=task_prompt, role="developer"),
            ),
        )

    def workflow_steps_for_yaml(self) -> WorkflowSteps:
        # Every WorkflowSteps slot is passed explicitly (None for unused) so the
        # wire form stays stable. See _ALL_STAGE_ATTRS.
        stage_steps: typing.Dict[str, typing.Optional[WorkflowStep]] = {
            attr: None for attr in _ALL_STAGE_ATTRS
        }
        groups_by_slot: typing.Dict[str, typing.List[str]] = {}
        for group_name, slot in self.group_slots.items():
            groups_by_slot.setdefault(slot, []).append(group_name)

        for slot, group_names in groups_by_slot.items():
            meta = SLOT_MENU[slot]
            cfg = self._step_config(group_names, meta)
            stage_steps[meta["stage"]] = WorkflowStep(
                all_=None,
                figure=cfg,
                paragraph=cfg,
                json_=None,
                table=None,
                table_figure=cfg,
            )
        return WorkflowSteps(**stage_steps)


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
    group_slots = _resolve_group_slots(prepared)
    filtered_path = _write_prepared_workflow_yaml(prepared.workflow_groups, yaml_dir)
    filtered_basename = os.path.splitext(os.path.basename(filtered_path))[0]

    api_key = os.environ.get("GROUNDX_API_KEY", "compile-only-not-used")
    base_url = os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api")
    gx = GroundX(api_key=api_key, base_url=base_url)

    logger = Logger(name="extractx-compile", level="warning")
    source = Source(logger=logger, cache_path=yaml_dir)
    wrapper_module = _load_wrapper_module(yaml_dir)

    try:
        runner = _CompileManager(
            model_id=os.environ.get("EXTRACT_MODEL_ID", "gpt-5-mini"),
            model_reasoning=os.environ.get("EXTRACT_MODEL_REASONING", "high"),
            service=os.environ.get("EXTRACT_MODEL_SERVICE", "openai"),
            group_slots=group_slots,
            wrapper_module=wrapper_module,
            cache_source=source,
            config_source=source,
            gx_client=gx,
            logger=logger,
            default_file_name=filtered_basename,
            default_workflow_id=filtered_basename,
        )

        workflow = {
            "name": resolved_name,
            "chunk_strategy": "element",
            "extract": _to_dict(runner.workflow_extract_dict()),
            "steps": _to_dict(runner.workflow_steps_for_yaml()),
        }
        return workflow, _metadata_from_prepared(yaml_path, raw_yaml, prepared)
    finally:
        try:
            os.remove(filtered_path)
        except OSError:
            pass


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
