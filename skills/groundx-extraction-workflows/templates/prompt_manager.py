#!/usr/bin/env python3
"""Minimal prompt-manager adapter for today's extraction pilots.

This template is intentionally small. It lets a project keep `prompt.yaml` as
the source of truth while using domain-specific wrapper modules for extract,
reconcile, and QA prompts. The future direction is for `groundx-python/extract`
to own more of this behavior directly; this file is the practical bridge for
projects that need a working flow now.

Expected wrapper convention:

- `prompt_statement_extract_request(field_specs: str) -> str`
- `prompt_statement_extract_task(field_descriptions: str) -> str`
- `prompt_meters_extract_request(field_specs: str, group_definition: str) -> str`
- `prompt_meters_extract_task(field_descriptions: str) -> str`
- `prompt_statement_reconcile(*args, **kwargs) -> str`
- `prompt_statement_qa(*args, **kwargs) -> str`

Repeating groups can follow the same naming pattern, for example
`prompt_charges_extract_request` and `prompt_charges_extract_task`.
"""

from __future__ import annotations

import json
import os
import time
import typing
from dataclasses import dataclass

from groundx import Document, GroundX

from compile_workflow import (
    build_workflow,
    workflow_sdk_kwargs,
    _repeating_request,
    _repeating_task,
    _singleton_request,
    _singleton_task,
)


@dataclass
class ExtractionRunArtifacts:
    workflow_id: str
    bucket_id: int
    process_id: str
    document_id: str
    extract: dict[str, typing.Any]
    xray: dict[str, typing.Any]


def _to_plain_dict(obj: typing.Any) -> dict[str, typing.Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True)
    if hasattr(obj, "dict"):
        return obj.dict(by_alias=True)
    return dict(obj)


def _value(obj: typing.Any, *names: str) -> typing.Any:
    current = obj
    for name in names:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(name)
        else:
            current = getattr(current, name, None)
    return current


def _workflow_id(response: typing.Any) -> str:
    workflow_id = (
        _value(response, "workflow", "workflow_id")
        or _value(response, "workflow", "workflowId")
        or _value(response, "workflow_id")
        or _value(response, "workflowId")
    )
    if not workflow_id:
        raise RuntimeError(f"workflow response did not include a workflow ID: {response!r}")
    return str(workflow_id)


class ExtractionWorkflowManager:
    """Small adapter around GroundX workflow lifecycle for extraction pilots."""

    def __init__(self, gx_client: GroundX) -> None:
        self.gx_client = gx_client

    def workflow_body(self, *, yaml_path: str, workflow_name: str | None = None) -> dict[str, typing.Any]:
        return build_workflow(yaml_path, name=workflow_name)

    def workflow_steps(self, *, yaml_path: str, workflow_name: str | None = None) -> dict[str, typing.Any]:
        workflow = self.workflow_body(yaml_path=yaml_path, workflow_name=workflow_name)
        return typing.cast(dict[str, typing.Any], workflow.get("steps", {}))

    def workflow_extract_dict(self, *, yaml_path: str, workflow_name: str | None = None) -> dict[str, typing.Any]:
        workflow = self.workflow_body(yaml_path=yaml_path, workflow_name=workflow_name)
        return typing.cast(dict[str, typing.Any], workflow.get("extract", {}))

    # These per-group methods are the override points for a custom manager
    # subclass (the EXTRACT_WRAPPER_MODULE convention). The defaults delegate to
    # the compiler's generic builders — `statement` is a singleton group,
    # `charges`/`meters` are repeating groups — so they track the domain-agnostic
    # compiler instead of bespoke per-group functions.
    def prompt_statement_extract_request(self, field_specs: str) -> str:
        return _singleton_request(field_specs)

    def prompt_statement_extract_task(self, field_descriptions: str) -> str:
        return _singleton_task(field_descriptions)

    def prompt_charges_extract_request(self, field_specs: str, group_definition: str) -> str:
        return _repeating_request("charges", field_specs, group_definition)

    def prompt_charges_extract_task(self, field_descriptions: str) -> str:
        return _repeating_task("charges", field_descriptions)

    def prompt_meters_extract_request(self, field_specs: str, group_definition: str) -> str:
        return _repeating_request("meters", field_specs, group_definition)

    def prompt_meters_extract_task(self, field_descriptions: str) -> str:
        return _repeating_task("meters", field_descriptions)

    def prompt_statement_reconcile(
        self,
        *,
        candidate_json: dict[str, typing.Any],
        xray_context: dict[str, typing.Any],
    ) -> str:
        return (
            "Compare the candidate extraction against the X-Ray evidence. "
            "Return only corrected JSON. Candidate JSON:\n"
            f"{json.dumps(candidate_json, indent=2, default=str)}\n\n"
            "X-Ray evidence:\n"
            f"{json.dumps(xray_context, indent=2, default=str)}"
        )

    def prompt_statement_qa(
        self,
        *,
        reconciled_json: dict[str, typing.Any],
        field_keys: list[str],
        field_prompts: dict[str, str],
    ) -> str:
        return (
            "Review the reconciled extraction for missing or unsupported fields. "
            "Return only JSON with the same top-level shape. Field keys:\n"
            f"{json.dumps(field_keys, indent=2)}\n\n"
            "Field prompts:\n"
            f"{json.dumps(field_prompts, indent=2)}\n\n"
            "Reconciled JSON:\n"
            f"{json.dumps(reconciled_json, indent=2, default=str)}"
        )

    def init_prompts(self, *, yaml_path: str, workflow_name: str | None = None) -> str:
        workflow = self.workflow_body(yaml_path=yaml_path, workflow_name=workflow_name)
        gx_client = typing.cast(typing.Any, self.gx_client)
        if hasattr(gx_client, "create_extraction_workflow"):
            response = gx_client.create_extraction_workflow(path=yaml_path, name=workflow["name"])
        else:
            response = self.gx_client.workflows.create(**workflow_sdk_kwargs(workflow))
        return _workflow_id(response)

    def update_prompts(
        self,
        *,
        workflow_id: str,
        yaml_path: str,
        workflow_name: str | None = None,
    ) -> str:
        workflow = self.workflow_body(yaml_path=yaml_path, workflow_name=workflow_name)
        gx_client = typing.cast(typing.Any, self.gx_client)
        if hasattr(gx_client, "update_extraction_workflow"):
            gx_client.update_extraction_workflow(workflow_id, path=yaml_path, name=workflow["name"])
        else:
            self.gx_client.workflows.update(
                id=workflow_id,
                **workflow_sdk_kwargs(workflow),
            )
        return workflow_id

    def check_workflow(self, *, workflow_id: str) -> dict[str, typing.Any]:
        return _to_plain_dict(self.gx_client.workflows.get(id=workflow_id))

    def list_workflows(self) -> dict[str, typing.Any]:
        return _to_plain_dict(self.gx_client.workflows.list())

    def add_to_account(self, *, workflow_id: str) -> None:
        self.gx_client.workflows.add_to_account(workflow_id=workflow_id)

    def remove_from_account(self) -> None:
        self.gx_client.workflows.remove_from_account()

    def add_to_id(self, *, bucket_id: int, workflow_id: str) -> None:
        self.gx_client.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)

    def remove_from_id(self, *, bucket_id: int) -> None:
        self.gx_client.workflows.remove_from_id(id=bucket_id)

    def ingest_and_debug(
        self,
        *,
        bucket_id: int,
        file_path: str,
        poll_interval_seconds: int = 15,
        max_polls: int = 120,
    ) -> ExtractionRunArtifacts:
        ingest_response = self.gx_client.ingest(
            documents=[
                Document(
                    bucket_id=bucket_id,
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    file_type=os.path.splitext(file_path)[1].lstrip(".") or "pdf",
                )
            ]
        )
        process_id = ingest_response.ingest.process_id
        document_id = self._poll_document_id(
            process_id=process_id,
            poll_interval_seconds=poll_interval_seconds,
            max_polls=max_polls,
        )
        extract = _to_plain_dict(self.gx_client.documents.get_extract(document_id=document_id))
        xray = _to_plain_dict(self.gx_client.documents.get_xray(document_id=document_id))
        return ExtractionRunArtifacts(
            workflow_id="",
            bucket_id=bucket_id,
            process_id=process_id,
            document_id=document_id,
            extract=extract,
            xray=xray,
        )

    def _poll_document_id(
        self,
        *,
        process_id: str,
        poll_interval_seconds: int,
        max_polls: int,
    ) -> str:
        for _ in range(max_polls):
            status = self.gx_client.documents.get_processing_status_by_id(process_id=process_id)
            if status.ingest.progress and status.ingest.progress.complete:
                documents = status.ingest.progress.complete.documents or []
                if documents:
                    return documents[0].document_id
            if status.ingest.status in ("error", "cancelled"):
                raise RuntimeError(f"ingest failed: {status.ingest.status}")
            time.sleep(poll_interval_seconds)
        raise TimeoutError(f"ingest did not complete for process_id={process_id}")


def dump_debug_artifacts(artifacts: ExtractionRunArtifacts, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "extract.json"), "w") as f:
        json.dump(artifacts.extract, f, indent=2, default=str)
    with open(os.path.join(out_dir, "xray.json"), "w") as f:
        json.dump(artifacts.xray, f, indent=2, default=str)
