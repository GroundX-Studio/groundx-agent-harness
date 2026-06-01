#!/usr/bin/env python3
"""Compile a YAML extraction schema into a GroundX workflow JSON.

Usage:
    python compile_workflow.py <prompt.yaml> [--name NAME] > workflow.json

Outputs the workflow JSON to stdout. Does NOT call any GroundX API —
this is a pure offline transformation. The output is the exact body
shape you POST to `/v1/workflow` (or pass to `gx.workflows.create()`,
or to the `workflow_create` MCP tool from the groundx-api skill).

Domain-agnostic group→slot mapping
----------------------------------
The compiler carries no hardcoded group names. Each top-level YAML key is a
group; its workflow slot is resolved by precedence:

  1. an explicit `slot:` on the group, then
  2. a top-level `domain:` whose profile (templates/domains/<domain>.yaml)
     supplies the group→slot map, then
  3. a hard error if neither is present.

Slots must be on the proven menu (SLOT_MENU): `chunk-instruct` (singleton
per-document object), `chunk-keys` and `chunk-summary` (repeating record
arrays). One group per slot. Reserved top-level keys (e.g. `domain`) and the
per-group `slot:` key are consumed locally and never reach the workflow JSON —
only `{name, chunk_strategy, extract, steps}` is sent to the platform.

Reads .env for EXTRACT_MODEL_* (engine config). No real GROUNDX_API_KEY is
needed because no API calls are made; a placeholder is acceptable.

For the actual API calls (workflow create, attach to bucket, ingest,
poll, retrieve extract), use the groundx-api skill — that is the
source of truth for those operations.
"""

import argparse
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

# Top-level YAML keys that are NOT groups. Consumed locally during compile.
RESERVED_TOP_LEVEL_KEYS = {"domain"}

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
}

# Domain profiles live next to this script.
DOMAINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domains")


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
    with open(path) as f:
        profile = yaml.safe_load(f) or {}
    groups = profile.get("groups") or {}
    if not isinstance(groups, dict) or not groups:
        raise ValueError(f"domain profile {path} has no `groups:` map")
    return {str(g): str(s) for g, s in groups.items()}


def _resolve_group_slots(raw: dict) -> "dict[str, str]":
    """Resolve each group's slot by precedence: explicit `slot:` → domain → error.

    Enforces the proven slot menu and one-group-per-slot.
    """
    domain = raw.get("domain")
    profile = _load_domain_profile(str(domain)) if domain else {}

    group_names = [k for k in raw.keys() if k not in RESERVED_TOP_LEVEL_KEYS]
    if not group_names:
        raise ValueError("no groups found in YAML (only reserved keys present)")

    resolved: dict[str, str] = {}
    used: dict[str, str] = {}
    for name in group_names:
        cfg = raw[name] if isinstance(raw[name], dict) else {}
        slot = cfg.get("slot") or profile.get(name)
        if not slot:
            raise ValueError(
                f"group '{name}' has no slot. Declare a `slot:` on the group "
                f"(one of {sorted(SLOT_MENU)}) or a top-level `domain:` whose "
                f"profile maps '{name}'."
            )
        if slot not in SLOT_MENU:
            raise ValueError(
                f"group '{name}' declares slot '{slot}', which is not on the "
                f"proven slot menu {sorted(SLOT_MENU)}."
            )
        if slot in used:
            raise ValueError(
                f"slot '{slot}' is mapped by both '{used[slot]}' and '{name}'. "
                f"Each slot carries exactly one group."
            )
        used[slot] = name
        resolved[name] = slot
    return resolved


def _write_filtered_yaml(raw: dict, yaml_dir: str) -> str:
    """Write a groups-only YAML (reserved top-level keys and per-group
    metadata keys stripped) so the SDK PromptManager parses only real groups
    and never sees the slot selector or business-logic metadata. Returns the
    temp file path (caller deletes it)."""
    filtered: dict = {}
    for key, value in raw.items():
        if key in RESERVED_TOP_LEVEL_KEYS:
            continue
        if isinstance(value, dict):
            filtered[key] = {
                k: v for k, v in value.items() if k not in _GROUP_METADATA_KEYS
            }
        else:
            filtered[key] = value
    fd, path = tempfile.mkstemp(dir=yaml_dir, prefix="_cf_", suffix=".yaml")
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(filtered, f, sort_keys=False, allow_unicode=True)
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

    def _step_config(self, group_name: str, slot_meta: dict) -> WorkflowStepConfig:
        if slot_meta["kind"] == "singleton":
            request_prompt = _call_wrapper(
                self.wrapper_module,
                _wrapper_names(group_name, "request"),
                _singleton_request,
                self.group_field_prompts(group_name),
            )
            task_prompt = _call_wrapper(
                self.wrapper_module,
                _wrapper_names(group_name, "task"),
                _singleton_task,
                self.group_descriptions(group_name),
            )
        else:  # repeating
            request_prompt = _call_wrapper(
                self.wrapper_module,
                _wrapper_names(group_name, "request"),
                lambda fs, gd: _repeating_request(group_name, fs, gd),
                self.group_field_prompts(group_name),
                self.group_definition(group_name),
            )
            task_prompt = _call_wrapper(
                self.wrapper_module,
                _wrapper_names(group_name, "task"),
                lambda fd: _repeating_task(group_name, fd),
                self.group_descriptions(group_name),
            )
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
        for group_name, slot in self.group_slots.items():
            meta = SLOT_MENU[slot]
            cfg = self._step_config(group_name, meta)
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


def build_workflow(yaml_path: str, name: typing.Optional[str] = None) -> dict:
    """Compile a YAML schema into a workflow JSON dict.

    Exposed for in-process callers (e.g. run_extraction.py) so they can
    skip the subprocess + file round-trip that the CLI entry point uses.
    """
    yaml_dir = os.path.dirname(os.path.abspath(yaml_path)) or "."
    yaml_basename = os.path.splitext(os.path.basename(yaml_path))[0]
    resolved_name = name or yaml_basename

    with open(yaml_path) as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{yaml_path}: top-level YAML must be a mapping of groups")

    group_slots = _resolve_group_slots(raw)
    filtered_path = _write_filtered_yaml(raw, yaml_dir)
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

        return {
            "name": resolved_name,
            "chunk_strategy": "element",
            "extract": _to_dict(runner.workflow_extract_dict()),
            "steps": _to_dict(runner.workflow_steps_for_yaml()),
        }
    finally:
        try:
            os.remove(filtered_path)
        except OSError:
            pass


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
