#!/usr/bin/env python3
"""Deploy a finished extraction YAML as a GroundX workflow.

Compiles a YAML with `compile_workflow.py`, validates the workflow JSON,
creates or updates the workflow through the GroundX Python SDK, and
optionally attaches it to a bucket or the account default. This is a
deploy-only command; use `run_extraction.py` when you also need ingest,
polling, X-Ray, and extraction output.

Example:

    python deploy_workflow.py \
        --yaml prompt.yaml \
        --out deploy/ \
        --workflow-name customer-workflow-v1 \
        --create-bucket-name customer-bucket-v1

Reads `.env` from the current working directory and the YAML directory for
`GROUNDX_API_KEY` and optional `GROUNDX_BASE_URL`. Do not pass API keys as
command arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import typing

import dotenv
from groundx import GroundX

from compile_workflow import build_workflow_artifacts, workflow_sdk_kwargs
from validate_workflow_json import validate


def _abs(out: str, name: str) -> str:
    return os.path.join(out, name)


def _to_plain_dict(obj: typing.Any) -> dict[str, typing.Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return typing.cast(dict[str, typing.Any], obj.model_dump(by_alias=True))
    if hasattr(obj, "dict"):
        return typing.cast(dict[str, typing.Any], obj.dict(by_alias=True))
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


def _bucket_id(response: typing.Any) -> int:
    bucket_id = (
        _value(response, "bucket", "bucket_id")
        or _value(response, "bucket", "bucketId")
        or _value(response, "bucket_id")
        or _value(response, "bucketId")
    )
    if bucket_id is None:
        raise RuntimeError(f"bucket response did not include a bucket ID: {response!r}")
    return int(bucket_id)


def _bucket_item_id(bucket: typing.Any) -> int | None:
    bucket_id = _value(bucket, "bucket_id") or _value(bucket, "bucketId")
    return int(bucket_id) if bucket_id is not None else None


def _bucket_item_name(bucket: typing.Any) -> str | None:
    name = _value(bucket, "name")
    return str(name) if name is not None else None


def _bucket_list_items(response: typing.Any) -> list[typing.Any]:
    buckets = _value(response, "buckets")
    if buckets is None:
        return []
    return list(buckets)


def _next_token(response: typing.Any) -> str | None:
    token = _value(response, "next_token") or _value(response, "nextToken")
    return str(token) if token else None


def _load_environment(yaml_path: str) -> None:
    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
    yaml_env = os.path.join(os.path.dirname(os.path.abspath(yaml_path)), ".env")
    if os.path.exists(yaml_env):
        dotenv.load_dotenv(yaml_env)


def _load_client(yaml_path: str) -> GroundX:
    _load_environment(yaml_path)
    api_key = os.environ.get("GROUNDX_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: GROUNDX_API_KEY is not set")
    return GroundX(
        api_key=api_key,
        base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
    )


def _compile_workflow(yaml_path: str, workflow_name: str, out: str, skip_validate: bool) -> dict[str, typing.Any]:
    if not os.path.exists(yaml_path):
        raise SystemExit(f"ERROR: YAML file not found: {yaml_path}")

    workflow, extraction_metadata = build_workflow_artifacts(yaml_path, name=workflow_name)
    workflow_json_path = _abs(out, "workflow.json")
    with open(workflow_json_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, default=str)
    with open(_abs(out, "extraction_workflow_metadata_v1.json"), "w", encoding="utf-8") as f:
        json.dump(extraction_metadata, f, indent=2, default=str)

    if not skip_validate:
        errors = validate(workflow)
        if errors:
            raise SystemExit("workflow validation failed:\n  - " + "\n  - ".join(errors))

    return workflow


def _list_buckets_page(gx: GroundX, next_token: str | None) -> typing.Any:
    try:
        if next_token:
            return gx.buckets.list(n=100, next_token=next_token)
        return gx.buckets.list(n=100)
    except TypeError:
        if next_token:
            return gx.buckets.list(n=100, nextToken=next_token)
        return gx.buckets.list(n=100)


def _find_bucket_id_by_name(gx: GroundX, bucket_name: str) -> int:
    matches: list[int] = []
    next_token: str | None = None

    while True:
        response = _list_buckets_page(gx, next_token)
        for bucket in _bucket_list_items(response):
            if _bucket_item_name(bucket) == bucket_name:
                bucket_id = _bucket_item_id(bucket)
                if bucket_id is not None:
                    matches.append(bucket_id)

        next_token = _next_token(response)
        if not next_token:
            break

    if not matches:
        raise SystemExit(
            f"ERROR: no existing bucket named {bucket_name!r}. "
            "Use --create-bucket-name to create a new bucket."
        )
    if len(matches) > 1:
        raise SystemExit(
            f"ERROR: multiple buckets named {bucket_name!r}. "
            "Use --bucket-id to choose one explicitly."
        )
    return matches[0]


def _create_or_update_workflow(
    gx: GroundX,
    workflow: dict[str, typing.Any],
    yaml_path: str,
    workflow_id: str | None,
) -> tuple[str, str, typing.Any]:
    kwargs = workflow_sdk_kwargs(workflow)
    if workflow_id:
        response = gx.workflows.update(
            workflow_id,
            **kwargs,
        )
        return workflow_id, "updated", response

    response = gx.workflows.create(**kwargs)
    return _workflow_id(response), "created", response


def _delete_created_bucket(gx: GroundX, bucket_id: int) -> str | None:
    try:
        gx.buckets.delete(bucket_id=bucket_id)
    except Exception as exc:
        return str(exc)
    return None


def _write_metadata(out: str, metadata: dict[str, typing.Any]) -> None:
    with open(_abs(out, "deploy.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    if metadata.get("workflowId") is not None:
        with open(_abs(out, "workflow_id.txt"), "w", encoding="utf-8") as f:
            f.write(str(metadata["workflowId"]))
    if metadata.get("bucketId") is not None:
        with open(_abs(out, "bucket_id.txt"), "w", encoding="utf-8") as f:
            f.write(str(metadata["bucketId"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", required=True, help="Path to extraction YAML")
    parser.add_argument("--out", required=True, help="Deploy output directory")
    parser.add_argument("--workflow-name", default=None, help="Workflow name (default: derived from YAML)")
    parser.add_argument("--workflow-id", default=None, help="Existing workflow_id to update instead of creating")
    parser.add_argument("--bucket-id", type=int, default=None, help="Existing bucket_id to attach")
    parser.add_argument("--bucket-name", default=None, help="Existing bucket name to look up and attach")
    parser.add_argument("--create-bucket-name", default=None, help="Create a bucket with this name and attach")
    parser.add_argument("--add-to-account", action="store_true", help="Set workflow as account default")
    parser.add_argument("--dry-run", action="store_true", help="Compile, validate, and write planned actions without API calls")
    parser.add_argument("--skip-validate", action="store_true", help="Skip workflow JSON validation")
    args = parser.parse_args()

    bucket_targets = [
        args.bucket_id is not None,
        bool(args.bucket_name),
        bool(args.create_bucket_name),
    ]
    if sum(bucket_targets) > 1:
        raise SystemExit("ERROR: use only one of --bucket-id, --bucket-name, or --create-bucket-name")

    os.makedirs(args.out, exist_ok=True)
    workflow_name = args.workflow_name or os.path.splitext(os.path.basename(args.yaml))[0]
    workflow = _compile_workflow(args.yaml, workflow_name, args.out, args.skip_validate)

    if args.dry_run:
        planned_attachments = []
        if args.add_to_account:
            planned_attachments.append("account")
        if args.bucket_id is not None:
            planned_attachments.append(f"bucket_id:{args.bucket_id}")
        if args.bucket_name:
            planned_attachments.append(f"existing_bucket_name:{args.bucket_name}")
        if args.create_bucket_name:
            planned_attachments.append(f"create_bucket_name:{args.create_bucket_name}")
        planned_attachment = ", ".join(planned_attachments) if planned_attachments else "none"
        metadata = {
            "status": "dry-run",
            "workflowId": args.workflow_id,
            "workflowAction": "update" if args.workflow_id else "create",
            "workflowName": workflow["name"],
            "workflowJson": _abs(args.out, "workflow.json"),
            "plannedAttachment": planned_attachment,
        }
        _write_metadata(args.out, metadata)
        print(
            "dry-run ok. "
            f"workflow_action={metadata['workflowAction']} "
            f"target={planned_attachment} "
            f"out={args.out}"
        )
        return 0

    gx = _load_client(args.yaml)
    bucket_id: int | None = args.bucket_id
    if args.bucket_name:
        bucket_id = _find_bucket_id_by_name(gx, args.bucket_name)

    workflow_id, workflow_action, workflow_response = _create_or_update_workflow(
        gx,
        workflow,
        args.yaml,
        args.workflow_id,
    )

    created_bucket = False
    account_assigned = False
    attachment_error: str | None = None
    cleanup_error: str | None = None

    try:
        if args.add_to_account:
            gx.workflows.add_to_account(workflow_id=workflow_id)
            account_assigned = True

        if args.create_bucket_name:
            bucket_response = gx.buckets.create(name=args.create_bucket_name)
            bucket_id = _bucket_id(bucket_response)
            created_bucket = True

        if bucket_id is not None:
            gx.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)

    except Exception as exc:
        attachment_error = str(exc)
        if created_bucket and bucket_id is not None:
            cleanup_error = _delete_created_bucket(gx, bucket_id)
        metadata = {
            "status": "failed",
            "workflowId": workflow_id,
            "workflowAction": workflow_action,
            "workflowResponse": _to_plain_dict(workflow_response),
            "bucketId": bucket_id,
            "bucketCreated": created_bucket,
            "accountAssigned": account_assigned,
            "error": attachment_error,
            "cleanupError": cleanup_error,
        }
        _write_metadata(args.out, metadata)
        raise SystemExit(f"workflow deploy failed after workflow {workflow_action}: {attachment_error}")

    metadata = {
        "status": "deployed",
        "workflowId": workflow_id,
        "workflowAction": workflow_action,
        "workflowName": workflow["name"],
        "workflowResponse": _to_plain_dict(workflow_response),
        "workflowJson": _abs(args.out, "workflow.json"),
        "bucketId": bucket_id,
        "bucketName": args.bucket_name,
        "createdBucketName": args.create_bucket_name,
        "bucketCreated": created_bucket,
        "accountAssigned": account_assigned,
    }
    _write_metadata(args.out, metadata)

    target_parts = []
    if account_assigned:
        target_parts.append("account")
    if bucket_id is not None:
        target_parts.append(f"bucket {bucket_id}")
    target = ", ".join(target_parts) if target_parts else "no attachment"
    print(f"workflow {workflow_action}. workflow_id={workflow_id} target={target} out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
