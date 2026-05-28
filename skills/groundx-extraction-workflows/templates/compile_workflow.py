#!/usr/bin/env python3
"""Compile a YAML extraction schema into a GroundX workflow JSON.

Usage:
    python compile_workflow.py <prompt.yaml> [--name NAME] > workflow.json

Outputs the workflow JSON to stdout. Does NOT call any GroundX API —
this is a pure offline transformation. The output is the exact body
shape you POST to `/v1/workflow` (or pass to `gx.workflows.create()`,
or to the `workflow_create` MCP tool from the groundx-api skill).

Reads .env for EXTRACT_MODEL_* (engine config). The script does not
need a real GROUNDX_API_KEY because no API calls are made; a
placeholder is acceptable.

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
import typing

import dotenv

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


# --- Inline wrapper templates ---------------------------------------------


def _statement_request(field_specs: str) -> str:
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


def _statement_task(field_descriptions: str) -> str:
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


def _charges_request(field_specs: str, charge_definition: str) -> str:
    return f"""
# Request

Analyze the provided document content and extract every individual record.

# Extraction Guidelines

{charge_definition.strip()}

# Field Values

You must extract the following information for each record, if it can be
found.

{field_specs.strip()}

# Output shape

Return a single JSON object whose top-level key is `charges` and whose
value is a JSON array of record objects. Each record object uses the
field `Field` value (above) as its keys.

Example shape (illustrative — field names are placeholders, use the
real `Field` values from "Field Values" above):

```json
{{
  "charges": [
    {{"field_a": "value", "field_b": 123}},
    {{"field_a": "value", "field_b": 456}}
  ]
}}
```

If you cannot find any records in this content, return `{{"charges": []}}`.

DO NOT return a raw JSON array at the top level. DO NOT invent records
that are not visible in the content provided. Only include records you
can read directly from the document text or page images.

# Final Notes

- Use the value in `Field` as the JSON key inside each record.
- Exclude fields you cannot identify with confidence.
- Return only the JSON object — no commentary, no code fences.
"""


def _charges_task(field_descriptions: str) -> str:
    return f"""
# Identity

You are a structured-data assistant. Extract repeating records from documents
and return them as a JSON object with a `charges` array.

# Process

1. Identify each individual record (line item, charge, transaction) that
   is visible in the provided document content. Do not invent records.
2. For each record, look for the following fields:
{field_descriptions}
3. Build one JSON object per record with the `Field` values as keys.
4. Wrap the array of record objects in a top-level `{{"charges": [...]}}`
   object. Always use the `charges` key — never return a raw array,
   never use a different wrapper name.
5. If no records are found, return `{{"charges": []}}`.
6. Return only the resulting JSON object.
    """


def _meters_request(field_specs: str, meter_definition: str) -> str:
    return f"""
# Request

Analyze the provided document content and extract every physical meter or
metered-service usage record.

# Extraction Guidelines

{meter_definition.strip()}

# Field Values

You must extract the following information for each meter record, if it can be
found.

{field_specs.strip()}

# Output shape

Return a single JSON object whose top-level key is `meters` and whose value is
a JSON array of meter objects. Each meter object uses the field `Field` value
(above) as its keys.

Example shape (illustrative — field names are placeholders, use the real
`Field` values from "Field Values" above):

```json
{{
  "meters": [
    {{"meter_number": "A123", "usage": 42.5}},
    {{"meter_number": "B456", "usage": 17.2}}
  ]
}}
```

If you cannot find any meters in this content, return `{{"meters": []}}`.

DO NOT return a raw JSON array at the top level. DO NOT invent meters that are
not visible in the content provided. Only include records you can read directly
from the document text or page images.

# Final Notes

- Use the value in `Field` as the JSON key inside each meter record.
- Exclude fields you cannot identify with confidence.
- Return only the JSON object — no commentary, no code fences.
"""


def _meters_task(field_descriptions: str) -> str:
    return f"""
# Identity

You are a structured-data assistant. Extract physical meter or metered-service
usage records from documents and return them as a JSON object with a `meters`
array.

# Process

1. Identify each physical meter or metered-service usage record that is visible
   in the provided document content. Do not invent records.
2. For each meter record, look for the following fields:
{field_descriptions}
3. Build one JSON object per meter record with the `Field` values as keys.
4. Wrap the array of meter objects in a top-level `{{"meters": [...]}}`
   object. Always use the `meters` key — never return a raw array, never use a
   different wrapper name.
5. If no meters are found, return `{{"meters": []}}`.
6. Return only the resulting JSON object.
"""


def prompt_statement_extract_request(field_specs: str) -> str:
    return _statement_request(field_specs)


def prompt_statement_extract_task(field_descriptions: str) -> str:
    return _statement_task(field_descriptions)


def prompt_charges_extract_request(field_specs: str, charge_definition: str) -> str:
    return _charges_request(field_specs, charge_definition)


def prompt_charges_extract_task(field_descriptions: str) -> str:
    return _charges_task(field_descriptions)


def prompt_meters_extract_request(field_specs: str, meter_definition: str) -> str:
    return _meters_request(field_specs, meter_definition)


def prompt_meters_extract_task(field_descriptions: str) -> str:
    return _meters_task(field_descriptions)


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


# --- Compile helper -------------------------------------------------------


class _CompileManager(PromptManager):
    """PromptManager subclass used purely for offline YAML→JSON compilation."""

    def __init__(
        self,
        *,
        model_id: str,
        model_reasoning: typing.Optional[str],
        service: str,
        wrapper_module: typing.Any = None,
        **data: typing.Any,
    ) -> None:
        super().__init__(**data)
        self.model_id = model_id
        self.model_reasoning = model_reasoning
        self.service = service
        self.wrapper_module = wrapper_module

    def _engine(self) -> WorkflowEngine:
        return WorkflowEngine(
            engine_id=self.model_id,
            reasoning_effort=self.model_reasoning,
            service=self.service,
        )

    def _statement_step_config(self) -> WorkflowStepConfig:
        return WorkflowStepConfig(
            engine=self._engine(),
            field="sect-sum",
            includes={"pageImages": True},
            prompt=WorkflowPromptGroup(
                request=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_statement_extract_request",
                            "statement_extract_request",
                            "extract_statement_request",
                        ),
                        _statement_request,
                        self.group_field_prompts("statement"),
                    ),
                    role="user",
                ),
                task=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_statement_extract_task",
                            "statement_extract_task",
                            "extract_statement_task",
                        ),
                        _statement_task,
                        self.group_descriptions("statement"),
                    ),
                    role="developer",
                ),
            ),
        )

    def _charges_step_config(self) -> WorkflowStepConfig:
        return WorkflowStepConfig(
            engine=self._engine(),
            includes={"pageImages": True},
            prompt=WorkflowPromptGroup(
                request=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_charges_extract_request",
                            "charges_extract_request",
                            "extract_charges_request",
                        ),
                        _charges_request,
                        self.group_field_prompts("charges"),
                        self.group_definition("charges"),
                    ),
                    role="user",
                ),
                task=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_charges_extract_task",
                            "charges_extract_task",
                            "extract_charges_task",
                        ),
                        _charges_task,
                        self.group_descriptions("charges"),
                    ),
                    role="developer",
                ),
            ),
        )

    def _meters_step_config(self) -> WorkflowStepConfig:
        return WorkflowStepConfig(
            engine=self._engine(),
            field="chunk-sum",
            includes={"pageImages": True},
            prompt=WorkflowPromptGroup(
                request=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_meters_extract_request",
                            "meters_extract_request",
                            "extract_meters_request",
                        ),
                        _meters_request,
                        self.group_field_prompts("meters"),
                        self.group_definition("meters"),
                    ),
                    role="user",
                ),
                task=WorkflowPrompt(
                    prompt=_call_wrapper(
                        self.wrapper_module,
                        (
                            "prompt_meters_extract_task",
                            "meters_extract_task",
                            "extract_meters_task",
                        ),
                        _meters_task,
                        self.group_descriptions("meters"),
                    ),
                    role="developer",
                ),
            ),
        )

    def _has_top_level_group(self, group_name: str) -> bool:
        return group_name in self.get_fields_for_workflow()

    def _warn_missing_group(self, group_name: str, exc: Exception) -> None:
        print(
            f"[{self.default_file_name}] missing {group_name} definitions: {exc}",
            file=sys.stderr,
        )

    def workflow_steps_for_yaml(self) -> WorkflowSteps:
        # Every WorkflowStep variant and every WorkflowSteps slot must be
        # passed explicitly (None for unused). Pydantic v1's `.dict()` drops
        # unset fields, which produces a workflow JSON missing slot keys —
        # the platform then treats the workflow as partial and silently skips
        # extraction aggregators. See `_to_dict` below.
        statement_step = None
        charges_step = None
        meters_step = None
        try:
            cfg = self._statement_step_config()
            statement_step = WorkflowStep(
                all_=None,
                figure=cfg,
                paragraph=cfg,
                json_=None,
                table=None,
                table_figure=cfg,
            )
        except Exception as exc:
            self._warn_missing_group("statement", exc)
        try:
            cfg = self._charges_step_config()
            charges_step = WorkflowStep(
                all_=None,
                figure=cfg,
                paragraph=cfg,
                json_=None,
                table=None,
                table_figure=cfg,
            )
        except Exception as exc:
            self._warn_missing_group("charges", exc)
        if self._has_top_level_group("meters"):
            try:
                cfg = self._meters_step_config()
                meters_step = WorkflowStep(
                    all_=None,
                    figure=cfg,
                    paragraph=cfg,
                    json_=None,
                    table=None,
                    table_figure=cfg,
                )
            except Exception as exc:
                self._warn_missing_group("meters", exc)
        return WorkflowSteps(
            chunk_instruct=statement_step,
            chunk_keys=charges_step,
            chunk_summary=meters_step,
            doc_keys=None,
            doc_summary=None,
            sect_instruct=None,
            sect_summary=None,
        )


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

    api_key = os.environ.get("GROUNDX_API_KEY", "compile-only-not-used")
    base_url = os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api")
    gx = GroundX(api_key=api_key, base_url=base_url)

    logger = Logger(name="extractx-compile", level="warning")
    source = Source(logger=logger, cache_path=yaml_dir)
    wrapper_module = _load_wrapper_module(yaml_dir)

    runner = _CompileManager(
        model_id=os.environ.get("EXTRACT_MODEL_ID", "gpt-5-mini"),
        model_reasoning=os.environ.get("EXTRACT_MODEL_REASONING", "high"),
        service=os.environ.get("EXTRACT_MODEL_SERVICE", "openai"),
        wrapper_module=wrapper_module,
        cache_source=source,
        config_source=source,
        gx_client=gx,
        logger=logger,
        default_file_name=yaml_basename,
        default_workflow_id=resolved_name,
    )

    return {
        "name": resolved_name,
        "chunk_strategy": "element",
        "extract": _to_dict(runner.workflow_extract_dict()),
        "steps": _to_dict(runner.workflow_steps_for_yaml()),
    }


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
