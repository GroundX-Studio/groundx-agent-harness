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


# --- Compile helper -------------------------------------------------------


class _CompileManager(PromptManager):
    """PromptManager subclass used purely for offline YAML→JSON compilation."""

    def __init__(
        self,
        *,
        model_id: str,
        model_reasoning: typing.Optional[str],
        service: str,
        **data: typing.Any,
    ) -> None:
        super().__init__(**data)
        self.model_id = model_id
        self.model_reasoning = model_reasoning
        self.service = service

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
                    prompt=_statement_request(self.group_field_prompts("statement")),
                    role="user",
                ),
                task=WorkflowPrompt(
                    prompt=_statement_task(self.group_descriptions("statement")),
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
                    prompt=_charges_request(
                        self.group_field_prompts("charges"),
                        self.group_definition("charges"),
                    ),
                    role="user",
                ),
                task=WorkflowPrompt(
                    prompt=_charges_task(self.group_descriptions("charges")),
                    role="developer",
                ),
            ),
        )

    def workflow_steps_for_yaml(self) -> WorkflowSteps:
        # Every WorkflowStep variant and every WorkflowSteps slot must be
        # passed explicitly (None for unused). Pydantic v1's `.dict()` drops
        # unset fields, which produces a workflow JSON missing slot keys —
        # the platform then treats the workflow as partial and silently skips
        # the chunk_keys -> account_charges aggregator. See `_to_dict` below.
        statement_step = None
        charges_step = None
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
            self.logger.warning_msg(
                f"[{self.default_file_name}] missing statement definitions: {exc}",
                workflow_id=self.default_workflow_id,
            )
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
            self.logger.warning_msg(
                f"[{self.default_file_name}] missing charges definitions: {exc}",
                workflow_id=self.default_workflow_id,
            )
        return WorkflowSteps(
            chunk_instruct=statement_step,
            chunk_keys=charges_step,
            chunk_summary=None,
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

    runner = _CompileManager(
        model_id=os.environ.get("EXTRACT_MODEL_ID", "gpt-5-mini"),
        model_reasoning=os.environ.get("EXTRACT_MODEL_REASONING", "high"),
        service=os.environ.get("EXTRACT_MODEL_SERVICE", "openai"),
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
