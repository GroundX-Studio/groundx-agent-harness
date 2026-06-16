#!/usr/bin/env python3
"""Canonical end-to-end extraction runner.

Compiles a YAML, validates the compiled workflow JSON, creates a workflow
on GroundX, sets up a bucket, attaches the workflow, ingests the PDF,
polls to completion, captures X-Ray and extract, and writes everything
to the configured run directory. Emits structured JSONL events to
`<out>/run.log` so the run can be inspected after the script exits.

Replaces ~80 lines of repeated per-customer SDK orchestration code.
Customer run scripts can usually be a single invocation:

    python run_extraction.py \\
        --yaml prompt.yaml \\
        --pdf invoice.pdf \\
        --out v1/ \\
        --bucket-name extract-customer-v1

Reads `.env` (current directory) for `GROUNDX_API_KEY` and optional
`GROUNDX_BASE_URL`.

Optional flags:
    --reuse-workflow <id>  Skip workflow creation; attach existing workflow.
    --reuse-bucket <id>    Skip bucket creation; use existing bucket.
    --skip-validate        Skip validate_workflow_json check. Not recommended.
    --add-to-account       Also set the workflow as the account default
                           (some platform aggregations are gated on this).
    --poll-interval <sec>  Seconds between status polls (default: 15).
    --max-polls <n>        Maximum number of polls before timeout (default: 120).
"""

import argparse
import json
import os
import sys
import time
import typing

import dotenv

# Resolve .env from the user's cwd, not the script's __file__ tree.
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from groundx import Document, GroundX

# Sibling template imports (in-process — no subprocess overhead).
from business_logic import apply_business_logic
from compile_workflow import build_workflow_artifacts, workflow_sdk_kwargs
from run_log import RunLog
from validate_workflow_json import validate as validate_workflow
from xray_to_extract import xray_to_extract


def _load_business_logic_metadata(yaml_path: str) -> dict:
    """Extract per-group business-logic metadata from the extraction YAML.

    Returns `{group_name: {unique_attrs, match_attrs, conflict_attrs,
    passthrough}}` for every group that declares at least one such key. Groups
    with none are omitted, so a YAML carrying no business-logic metadata yields
    `{}` and `apply_business_logic` is a no-op (backward compatible).
    """
    try:
        _, metadata = build_workflow_artifacts(yaml_path)
    except Exception:
        return {}
    final_group_metadata = metadata.get("final_group_metadata")
    return final_group_metadata if isinstance(final_group_metadata, dict) else {}


def _abs(out: str, name: str) -> str:
    return os.path.join(out, name)


def _to_plain_dict(obj: typing.Any) -> dict:
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


def _compile(yaml_path: str, workflow_json_path: str, name: str, rl: RunLog) -> dict:
    rl.event("compile.start", yaml_path=yaml_path)
    workflow, metadata = build_workflow_artifacts(yaml_path, name=name)
    with open(workflow_json_path, "w") as f:
        json.dump(workflow, f, indent=2, default=str)
    metadata_path = os.path.join(
        os.path.dirname(workflow_json_path),
        "extraction_workflow_metadata_v1.json",
    )
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    rl.event("compile.done", workflow_json=workflow_json_path, metadata_json=metadata_path)
    return workflow


def _validate(workflow: dict, workflow_json_path: str, rl: RunLog) -> None:
    rl.event("validate.start", workflow_json=workflow_json_path)
    errors = validate_workflow(workflow)
    if errors:
        rl.event("validate.error", error_count=len(errors), errors=errors)
        raise SystemExit(
            "workflow validation failed:\n  - " + "\n  - ".join(errors)
        )
    rl.event("validate.done")


def _create_workflow(
    gx: GroundX,
    yaml_path: str,
    workflow: dict,
    workflow_name: str,
) -> typing.Any:
    return gx.workflows.create(**workflow_sdk_kwargs(workflow))


def _safe_delete(rl: RunLog, kind: str, fn: typing.Callable[[], typing.Any], **ids: typing.Any) -> None:
    try:
        fn()
        rl.event(f"cleanup.{kind}.deleted", **ids)
    except Exception as e:
        rl.event(f"cleanup.{kind}.error", error=str(e), **ids)


def _poll(gx: GroundX, process_id: str, interval: int, max_polls: int, rl: RunLog) -> typing.Optional[str]:
    document_id: typing.Optional[str] = None
    for i in range(max_polls):
        st = gx.documents.get_processing_status_by_id(process_id=process_id)
        status = st.ingest.status
        rl.event("ingest.poll", poll=i + 1, status=status)
        if st.ingest.progress:
            if st.ingest.progress.complete and st.ingest.progress.complete.documents:
                document_id = st.ingest.progress.complete.documents[0].document_id
            elif st.ingest.progress.processing and st.ingest.progress.processing.documents:
                document_id = st.ingest.progress.processing.documents[0].document_id
        if status == "complete":
            return document_id
        if status in ("error", "cancelled"):
            rl.event("ingest.failed", status=status, detail=str(st.ingest))
            raise SystemExit(f"ingest failed: {status}")
        time.sleep(interval)
    rl.event("ingest.timeout", polls=max_polls, interval=interval)
    raise SystemExit("ingest timed out")


def extract_from_document(
    gx: GroundX,
    document_id: str,
    bl_metadata: typing.Optional[dict] = None,
    rl: typing.Optional[RunLog] = None,
    workflow_extract: typing.Optional[dict] = None,
) -> typing.Tuple[dict, dict, str]:
    """Given an ingested document_id, derive its extraction. Returns
    (extract, xray, source). Shared by run_extraction (single doc) and
    batch_extraction (per doc) so the get_extract/X-Ray-fallback/business-logic
    logic lives in exactly one place.

    `get_extract` returns the server-side doc-level artifact. On deployments
    without the extract microservice it either 404s OR returns a truthy-but-
    incomplete object lacking the chunk-level repeating arrays (charges/meters),
    so trust it only when it carries populated records; otherwise aggregate the
    captured X-Ray locally (`xray_to_extract` reproduces the same shape). See
    references/6_known_limitations.md §4.
    """
    xray = _to_plain_dict(gx.documents.get_xray(document_id=document_id))
    source = "get_extract"
    try:
        fetched = _to_plain_dict(gx.documents.get_extract(document_id=document_id))
    except Exception as e:
        fetched = None
        if rl:
            rl.event("extract.get_extract_unavailable", reason=str(e)[:200])
    if fetched and any(isinstance(v, list) and v for v in fetched.values()):
        extract = fetched
    else:
        extract = xray_to_extract(xray, workflow_extract=workflow_extract)
        source = "xray_to_extract"
    if bl_metadata:
        extract = apply_business_logic(extract, bl_metadata)
        if rl:
            rl.event("business_logic.applied", groups=sorted(bl_metadata.keys()))
    return extract, xray, source


def _has_extracted_value(value: typing.Any) -> bool:
    return value not in (None, "", [])


def _extract_group_counts(extract_dict: dict) -> dict[str, int]:
    """Return a domain-neutral summary of top-level extraction output."""
    counts: dict[str, int] = {}
    for group, value in extract_dict.items():
        if isinstance(value, list):
            counts[group] = len(value)
        elif isinstance(value, dict):
            counts[group] = sum(
                1 for field_value in value.values() if _has_extracted_value(field_value)
            )
        else:
            counts[group] = 1 if _has_extracted_value(value) else 0
    return counts


def _format_group_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ",".join(f"{group}={count}" for group, count in counts.items())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", required=True, help="Path to extraction YAML")
    parser.add_argument("--pdf", required=True, help="Path to PDF to ingest")
    parser.add_argument("--out", required=True, help="Run output directory")
    parser.add_argument("--bucket-name", required=True, help="Bucket name to create")
    parser.add_argument("--workflow-name", default=None, help="Workflow name (default: derived from YAML)")
    parser.add_argument("--reuse-workflow", default=None, help="Existing workflow_id to reuse")
    parser.add_argument("--reuse-bucket", type=int, default=None, help="Existing bucket_id to reuse")
    parser.add_argument("--skip-validate", action="store_true", help="Skip workflow JSON validation")
    parser.add_argument("--add-to-account", action="store_true", help="Set workflow as account default")
    parser.add_argument("--poll-interval", type=int, default=15, help="Seconds between status polls")
    parser.add_argument("--max-polls", type=int, default=120, help="Max status polls before timeout")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    workflow_name = args.workflow_name or os.path.splitext(os.path.basename(args.yaml))[0]
    workflow_json_path = _abs(args.out, "workflow.json")
    xray_path = _abs(args.out, "xray.json")
    extract_path = _abs(args.out, "output.json")

    api_key = os.environ.get("GROUNDX_API_KEY")
    if not api_key:
        print("ERROR: GROUNDX_API_KEY is not set", file=sys.stderr)
        return 2

    gx = GroundX(
        api_key=api_key,
        base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
    )

    with RunLog(_abs(args.out, "run.log")) as rl:
        rl.event("run.start", yaml=args.yaml, pdf=args.pdf, out=args.out, bucket_name=args.bucket_name)
        rl.quota_snapshot(gx, label="run.start")

        # Setup phase — workflow create + bucket create + attach.
        # Anything we create here is rolled back on failure to prevent
        # orphan resources on the platform. Once attach succeeds, the
        # resources are "useful" (a workflow attached to a bucket) and
        # we stop the rollback boundary; ingest/poll failures keep
        # them around for inspection.
        workflow_id: typing.Optional[str] = None
        bucket_id: typing.Optional[int] = None
        created_workflow_id: typing.Optional[str] = None
        created_bucket_id: typing.Optional[int] = None
        workflow_extract: typing.Optional[dict] = None

        try:
            if args.reuse_workflow:
                workflow_id = args.reuse_workflow
                definition_loader = getattr(gx, "load_extraction_definition", None)
                if callable(definition_loader):
                    definition = definition_loader(workflow_id=workflow_id)
                    workflow_extract = getattr(definition, "extract", None)
                else:
                    workflow_loader = getattr(
                        gx, "load_extraction_definition_from_workflow", None
                    )
                    if callable(workflow_loader):
                        definition = workflow_loader(workflow_id)
                        workflow_extract = getattr(definition, "extract", None)
                rl.event("workflow.reuse", workflow_id=workflow_id)
            else:
                wf_body = _compile(args.yaml, workflow_json_path, workflow_name, rl)
                workflow_extract = wf_body.get("extract")
                if not args.skip_validate:
                    _validate(wf_body, workflow_json_path, rl)
                create_resp = _create_workflow(gx, args.yaml, wf_body, workflow_name)
                workflow_id = _workflow_id(create_resp)
                created_workflow_id = workflow_id
                rl.event("workflow.create", workflow_id=workflow_id, workflow_name=wf_body["name"])
                with open(_abs(args.out, "workflow_id.txt"), "w") as f:
                    f.write(workflow_id)

            if args.add_to_account:
                resp = gx.workflows.add_to_account(workflow_id=workflow_id)
                rl.event("workflow.add_to_account", result=str(resp))

            if args.reuse_bucket:
                bucket_id = args.reuse_bucket
                rl.event("bucket.reuse", bucket_id=bucket_id)
            else:
                bk = gx.buckets.create(name=args.bucket_name)
                bucket_id = bk.bucket.bucket_id
                created_bucket_id = bucket_id
                rl.event("bucket.create", bucket_id=bucket_id, bucket_name=args.bucket_name)
                with open(_abs(args.out, "bucket_id.txt"), "w") as f:
                    f.write(str(bucket_id))

            # Past this point, resources are attached and no longer orphans.
            gx.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)
            rl.event("workflow.add_to_bucket", bucket_id=bucket_id, workflow_id=workflow_id)

        except BaseException as setup_exc:
            rl.event("setup.failed", error=str(setup_exc), error_type=type(setup_exc).__name__)
            if created_workflow_id:
                _safe_delete(rl, "workflow", lambda: gx.workflows.delete(id=created_workflow_id), workflow_id=created_workflow_id)
            if created_bucket_id:
                _safe_delete(rl, "bucket", lambda: gx.buckets.delete(bucket_id=created_bucket_id), bucket_id=created_bucket_id)
            raise

        ingest_resp = gx.ingest(
            documents=[
                Document(
                    bucket_id=bucket_id,
                    file_path=args.pdf,
                    file_name=os.path.basename(args.pdf),
                    file_type="pdf",
                )
            ]
        )
        process_id = ingest_resp.ingest.process_id
        rl.event("ingest.start", process_id=process_id, pdf=args.pdf)
        with open(_abs(args.out, "process_id.txt"), "w") as f:
            f.write(process_id)

        document_id = _poll(gx, process_id, args.poll_interval, args.max_polls, rl)
        rl.event("ingest.complete", document_id=document_id)
        if document_id:
            with open(_abs(args.out, "document_id.txt"), "w") as f:
                f.write(document_id)

        # Derive the extraction (get_extract when populated, else aggregate the
        # X-Ray) + apply per-group business logic. Shared with batch_extraction.
        # A YAML with no business-logic keys yields {} -> the call is a no-op and
        # output.json is unchanged (backward compatible).
        bl_metadata = _load_business_logic_metadata(args.yaml)
        extract_dict, xray_dict, extract_source = extract_from_document(
            gx,
            document_id,
            bl_metadata,
            rl,
            workflow_extract=workflow_extract,
        )
        with open(xray_path, "w") as f:
            json.dump(xray_dict, f, indent=2, default=str)
        rl.event("xray.captured", path=xray_path, chunks=len(xray_dict.get("chunks") or []))

        with open(extract_path, "w") as f:
            json.dump(extract_dict, f, indent=2, default=str)
        group_counts = _extract_group_counts(extract_dict)
        rl.event("extract.captured", path=extract_path, source=extract_source, group_counts=group_counts)

        rl.quota_snapshot(gx, label="run.end")
        rl.event("run.done", group_counts=group_counts)

    print(
        f"run complete. out={args.out} document_id={document_id} "
        f"groups={_format_group_counts(group_counts)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
