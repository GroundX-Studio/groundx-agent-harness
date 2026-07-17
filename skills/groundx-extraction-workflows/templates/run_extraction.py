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
    --require-raw-extract  Fail if GroundX get_extract is unavailable. The
                           runner still writes X-Ray diagnostic artifacts.
    --resume               Resume polling from an existing run directory.
    --poll-interval <sec>  Seconds between status polls (default: 15).
    --max-polls <n>        Maximum number of polls before timeout (default: 120).
    --callback-url <url>    Optional ingest callback URL.
    --callback-data <str>   Optional callback data echoed by GroundX callbacks.
"""

import argparse
import json
import os
import shlex
import sys
import time
import typing
import urllib.parse

import dotenv

# Resolve .env from the user's cwd, not the script's __file__ tree.
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from groundx import Document, GroundX

# Sibling template imports (in-process — no subprocess overhead).
from business_logic import apply_business_logic
from compile_workflow import build_workflow_artifacts, workflow_sdk_kwargs
from estimate_workflow_requests import DEFAULT_CAP, count_pdf_pages, estimate_request_fanout
from run_log import RunLog
from validate_workflow_json import validate as validate_workflow
from xray_to_extract import xray_reassembly_artifacts


TIMEOUT_HISTORY_LIMIT = 10
BUSINESS_LOGIC_METADATA_FILENAME = "business_logic_metadata.json"
TRANSIENT_STATUS_ERROR_NAMES = {
    "ConnectError",
    "ConnectTimeout",
    "NetworkError",
    "ReadError",
    "ReadTimeout",
    "RemoteProtocolError",
    "TimeoutException",
    "TransportError",
    "WriteError",
    "WriteTimeout",
}


def _is_transient_status_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    module = exc.__class__.__module__
    name = exc.__class__.__name__
    return name in TRANSIENT_STATUS_ERROR_NAMES and (
        module.startswith("httpx") or module.startswith("httpcore")
    )


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


def _write_business_logic_metadata_for_run(
    out_dir: str,
    metadata: dict,
    rl: typing.Optional[RunLog] = None,
) -> None:
    path = _abs(out_dir, BUSINESS_LOGIC_METADATA_FILENAME)
    payload = metadata if isinstance(metadata, dict) else {}
    _write_json(path, payload)
    if rl:
        rl.event(
            "business_logic.metadata_saved",
            path=path,
            groups=sorted(payload.keys()),
        )


def _load_business_logic_metadata_from_run(
    out_dir: str,
    rl: typing.Optional[RunLog] = None,
) -> dict:
    path = _abs(out_dir, BUSINESS_LOGIC_METADATA_FILENAME)
    metadata = _read_json(path)
    payload = metadata if isinstance(metadata, dict) else {}
    if rl:
        rl.event(
            "business_logic.metadata_loaded",
            path=path if isinstance(metadata, dict) else None,
            groups=sorted(payload.keys()),
        )
    return payload


def _abs(out: str, name: str) -> str:
    return os.path.join(out, name)


def _read_text(path: str) -> typing.Optional[str]:
    try:
        with open(path, "r") as f:
            value = f.read().strip()
        return value or None
    except FileNotFoundError:
        return None


def _read_json(path: str) -> typing.Any:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_json(path: str, payload: typing.Any) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)


def _enforce_request_estimate_report(
    rl: RunLog,
    out_dir: str,
    report: dict,
    *,
    allow_high_request_estimate: bool,
) -> bool:
    _write_json(_abs(out_dir, "request_estimate.json"), report)
    status = report.get("risk_status")
    max_requests = report.get("max_estimated_requests")
    rl.event(
        "request_estimate.report",
        risk_status=status,
        max_estimated_requests=max_requests,
        output=_abs(out_dir, "request_estimate.json"),
    )
    if status == "warning":
        rl.event("request_estimate.warning", max_estimated_requests=max_requests)
    if status in {"block", "unknown_high_risk"}:
        rl.event(
            "request_estimate.block",
            risk_status=status,
            max_estimated_requests=max_requests,
            recommended_action=report.get("recommended_action"),
        )
        if allow_high_request_estimate:
            rl.event("request_estimate.override", risk_status=status)
            return True
        print(
            "ERROR: request estimate blocks this live extraction "
            f"({status}, max={max_requests}). "
            f"{report.get('recommended_action', 'Change strategy or pass --allow-high-request-estimate.')}",
            file=sys.stderr,
        )
        return False
    return True


def _request_estimate_preflight(
    rl: RunLog,
    out_dir: str,
    workflow: dict,
    pdf_paths: list[str],
    *,
    allow_high_request_estimate: bool,
) -> bool:
    try:
        page_counts = [count_pdf_pages(path) for path in pdf_paths]
    except Exception as exc:
        rl.event("request_estimate.error", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return False
    report = estimate_request_fanout(workflow, page_counts=page_counts)
    return _enforce_request_estimate_report(
        rl,
        out_dir,
        report,
        allow_high_request_estimate=allow_high_request_estimate,
    )


def _load_reused_workflow_extract(
    gx: GroundX,
    workflow_id: str,
) -> typing.Optional[dict]:
    definition_loader = getattr(gx, "load_extraction_definition", None)
    if callable(definition_loader):
        definition = definition_loader(workflow_id=workflow_id)
        workflow_extract = getattr(definition, "extract", None)
        return workflow_extract if isinstance(workflow_extract, dict) else None
    workflow_loader = getattr(gx, "load_extraction_definition_from_workflow", None)
    if callable(workflow_loader):
        definition = workflow_loader(workflow_id)
        workflow_extract = getattr(definition, "extract", None)
        return workflow_extract if isinstance(workflow_extract, dict) else None
    return None


def _load_workflow_extract_from_run(out_dir: str) -> typing.Optional[dict]:
    workflow = _read_json(_abs(out_dir, "workflow.json"))
    if not isinstance(workflow, dict):
        return None
    extract = workflow.get("extract")
    if isinstance(extract, dict):
        return extract
    compiled_keys = {
        "customSteps",
        "custom_steps",
        "outputRoutes",
        "output_routes",
        "leafFields",
        "leaf_fields",
    }
    if any(key in workflow for key in compiled_keys):
        return workflow
    return None


def _write_output_provenance(out_dir: str, *, process_id: str, document_id: str) -> None:
    _write_json(
        _abs(out_dir, "output_provenance.json"),
        {
            "artifact": "output.json",
            "kind": "raw_get_extract",
            "process_id": process_id,
            "document_id": document_id,
        },
    )


def _redacted_url(url: typing.Optional[str]) -> typing.Optional[str]:
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return "[invalid-url]"
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


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


def _documents_from_progress_group(progress: typing.Any, group_name: str) -> list:
    group = _value(progress, group_name)
    documents = _value(group, "documents")
    return documents if isinstance(documents, list) else []


def _document_id_from_progress_doc(document: typing.Any) -> typing.Optional[str]:
    document_id = (
        _value(document, "document_id")
        or _value(document, "documentId")
        or _value(document, "id")
    )
    return str(document_id) if document_id not in (None, "") else None


def _document_error_message(document: typing.Any) -> str:
    message = (
        _value(document, "status_message")
        or _value(document, "statusMessage")
        or _value(document, "message")
        or _value(document, "error")
    )
    document_id = _document_id_from_progress_doc(document)
    if document_id and message:
        return f"{document_id}: {message}"
    if document_id:
        return document_id
    return str(message or document)


def _progress_error_documents(progress: typing.Any) -> list:
    documents = _documents_from_progress_group(progress, "errors")
    if documents:
        return documents
    return _documents_from_progress_group(progress, "failed")


def _progress_error_total(progress: typing.Any) -> int:
    for group_name in ("errors", "failed"):
        group = _value(progress, group_name)
        total = _value(group, "total")
        if total in (None, ""):
            continue
        try:
            return int(total)
        except (TypeError, ValueError):
            continue
    return 0


def _progress_group_count(progress: typing.Any, group_name: str) -> int:
    group = _value(progress, group_name)
    total = _value(group, "total")
    if total not in (None, ""):
        try:
            return int(total)
        except (TypeError, ValueError):
            pass
    return len(_documents_from_progress_group(progress, group_name))


def _progress_counts(progress: typing.Any) -> dict[str, int]:
    if not progress:
        return {"complete": 0, "processing": 0, "errors": 0}
    return {
        "complete": _progress_group_count(progress, "complete"),
        "processing": _progress_group_count(progress, "processing"),
        "errors": _progress_group_count(progress, "errors")
        or _progress_group_count(progress, "failed"),
    }


def _timeout_scoreability(
    out_dir: str,
    *,
    process_id: str,
    document_id: typing.Optional[str],
) -> dict:
    output_path = _abs(out_dir, "output.json")
    provenance = _read_json(_abs(out_dir, "output_provenance.json"))
    output_exists = os.path.exists(output_path)
    result = {
        "output_json_exists": output_exists,
        "scoreable": False,
        "scoreability_reason": "raw output missing",
    }
    if not output_exists:
        return result
    if not isinstance(provenance, dict):
        result["scoreability_reason"] = "raw output provenance missing"
        return result
    if provenance.get("process_id") != process_id:
        result["scoreability_reason"] = "raw output provenance does not match this process"
        return result
    if document_id and provenance.get("document_id") != document_id:
        result["scoreability_reason"] = "raw output provenance does not match this document"
        return result
    if provenance.get("kind") not in (None, "raw_get_extract"):
        result["scoreability_reason"] = "output.json is not labeled as raw get_extract"
        return result
    result["scoreable"] = True
    result["scoreability_reason"] = "raw output provenance matches this process"
    return result


def _record_timeout_summary(
    out_dir: str,
    *,
    process_id: str,
    workflow_id: typing.Optional[str],
    bucket_id: typing.Optional[typing.Union[int, str]],
    elapsed_seconds: float,
    poll_count: int,
    poll_interval: int,
    last_status: typing.Optional[str],
    progress_counts: dict[str, int],
    document_id: typing.Optional[str],
) -> dict:
    scoreability = _timeout_scoreability(
        out_dir,
        process_id=process_id,
        document_id=document_id,
    )
    summary = {
        "process_id": process_id,
        "workflow_id": workflow_id,
        "bucket_id": bucket_id,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "poll_count": poll_count,
        "poll_interval_seconds": poll_interval,
        "last_status": last_status,
        "progress_counts": progress_counts,
        "resume_command": f"python run_extraction.py --resume --out {shlex.quote(out_dir)}",
        **scoreability,
    }
    _write_json(_abs(out_dir, "timeout_summary.json"), summary)

    history_path = _abs(out_dir, "timeout_history.json")
    existing = _read_json(history_path)
    history = existing if isinstance(existing, list) else []
    history = history[-(TIMEOUT_HISTORY_LIMIT - 1):] + [summary]
    _write_json(history_path, history)
    return summary


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


def _poll(
    gx: GroundX,
    process_id: str,
    interval: int,
    max_polls: int,
    rl: RunLog,
    *,
    out_dir: typing.Optional[str] = None,
    workflow_id: typing.Optional[str] = None,
    bucket_id: typing.Optional[typing.Union[int, str]] = None,
    started_at: typing.Optional[float] = None,
    now_fn: typing.Callable[[], float] = time.time,
) -> str:
    document_id: typing.Optional[str] = None
    start = started_at if started_at is not None else now_fn()
    last_status: typing.Optional[str] = None
    last_progress_counts = {"complete": 0, "processing": 0, "errors": 0}
    for i in range(max_polls):
        try:
            st = gx.documents.get_processing_status_by_id(process_id=process_id)
        except Exception as exc:
            if not _is_transient_status_error(exc):
                raise
            rl.event(
                "ingest.poll_error",
                poll=i + 1,
                error_type=exc.__class__.__name__,
                error=str(exc)[:200],
            )
            time.sleep(interval)
            continue
        status = st.ingest.status
        last_status = status
        rl.event("ingest.poll", poll=i + 1, status=status)
        progress = st.ingest.progress
        if progress:
            last_progress_counts = _progress_counts(progress)
            error_documents = _progress_error_documents(progress)
            if error_documents:
                details = [_document_error_message(document) for document in error_documents]
                rl.event("ingest.failed", status=status, detail="; ".join(details))
                raise SystemExit("ingest completed with document errors: " + "; ".join(details))
            error_total = _progress_error_total(progress)
            if error_total:
                detail = f"{error_total} document error"
                if error_total != 1:
                    detail += "s"
                detail += " reported in progress.errors"
                rl.event("ingest.failed", status=status, detail=detail)
                raise SystemExit("ingest completed with " + detail)
            complete_documents = _documents_from_progress_group(progress, "complete")
            processing_documents = _documents_from_progress_group(progress, "processing")
            if complete_documents:
                document_id = _document_id_from_progress_doc(complete_documents[0])
            elif processing_documents:
                document_id = _document_id_from_progress_doc(processing_documents[0])
        if status == "complete":
            if not document_id:
                detail = "ingest completed with no completed document ID"
                rl.event("ingest.failed", status=status, detail=detail)
                raise SystemExit(detail)
            return document_id
        if status in ("error", "cancelled"):
            rl.event("ingest.failed", status=status, detail=str(st.ingest))
            raise SystemExit(f"ingest failed: {status}")
        time.sleep(interval)
    summary = None
    if out_dir:
        summary = _record_timeout_summary(
            out_dir,
            process_id=process_id,
            workflow_id=workflow_id,
            bucket_id=bucket_id,
            elapsed_seconds=now_fn() - start,
            poll_count=max_polls,
            poll_interval=interval,
            last_status=last_status,
            progress_counts=last_progress_counts,
            document_id=document_id,
        )
    rl.event(
        "ingest.timeout",
        polls=max_polls,
        interval=interval,
        timeout_summary=_abs(out_dir, "timeout_summary.json") if out_dir else None,
        scoreable=summary.get("scoreable") if summary else None,
    )
    if summary:
        raise SystemExit(
            "ingest timed out: local polling expired; the platform process may still be "
            "running and is not scoreable until it completes with raw output. "
            f"resume polling the same process with: {summary['resume_command']}"
        )
    raise SystemExit("ingest timed out")


def derive_extraction_artifacts(
    gx: GroundX,
    document_id: str,
    bl_metadata: typing.Optional[dict] = None,
    rl: typing.Optional[RunLog] = None,
    workflow_extract: typing.Optional[dict] = None,
) -> dict:
    """Capture raw extract, X-Ray diagnostics, and final local output separately."""
    xray = _to_plain_dict(gx.documents.get_xray(document_id=document_id))
    raw_extract = None
    diagnostic_extract = None
    reassembly_diagnostic = None
    final_output = None
    source = "get_extract"

    try:
        fetched = _to_plain_dict(gx.documents.get_extract(document_id=document_id))
    except Exception as e:
        fetched = None
        if rl:
            rl.event("extract.get_extract_unavailable", reason=str(e)[:200])

    if isinstance(fetched, dict) and fetched:
        raw_extract = fetched
        if workflow_extract:
            reassembly_diagnostic = xray_reassembly_artifacts(
                xray,
                workflow_extract=workflow_extract,
            )
        if bl_metadata:
            final_output = apply_business_logic(raw_extract, bl_metadata)
            if rl:
                rl.event("business_logic.applied", groups=sorted(bl_metadata.keys()))
    else:
        if isinstance(fetched, dict) and rl:
            rl.event("extract.get_extract_empty")
        reassembly_diagnostic = xray_reassembly_artifacts(
            xray,
            workflow_extract=workflow_extract,
        )
        diagnostic_extract = reassembly_diagnostic["final_output"]
        final_output = diagnostic_extract
        source = "xray_to_extract"
        if bl_metadata:
            final_output = apply_business_logic(diagnostic_extract, bl_metadata)
            if rl:
                rl.event("business_logic.applied", groups=sorted(bl_metadata.keys()))

    return {
        "raw_extract": raw_extract,
        "xray": xray,
        "diagnostic_extract": diagnostic_extract,
        "reassembly_diagnostic": reassembly_diagnostic,
        "final_output": final_output,
        "source": source,
    }


def extract_from_document(
    gx: GroundX,
    document_id: str,
    bl_metadata: typing.Optional[dict] = None,
    rl: typing.Optional[RunLog] = None,
    workflow_extract: typing.Optional[dict] = None,
) -> typing.Tuple[dict, dict, str]:
    """Compatibility wrapper returning the best usable local output."""
    artifacts = derive_extraction_artifacts(
        gx,
        document_id,
        bl_metadata,
        rl,
        workflow_extract=workflow_extract,
    )
    extract = (
        artifacts["final_output"]
        or artifacts["raw_extract"]
        or artifacts["diagnostic_extract"]
        or {}
    )
    return extract, artifacts["xray"], artifacts["source"]


def _has_countable_extracted_value(value: typing.Any) -> bool:
    return value not in (None, "", [])


def _extract_group_counts(extract_dict: dict) -> dict[str, int]:
    """Return a domain-neutral summary of top-level extraction output."""
    counts: dict[str, int] = {}
    for group, value in extract_dict.items():
        if isinstance(value, list):
            counts[group] = len(value)
        elif isinstance(value, dict):
            counts[group] = sum(
                1
                for field_value in value.values()
                if _has_countable_extracted_value(field_value)
            )
        else:
            counts[group] = 1 if _has_countable_extracted_value(value) else 0
    return counts


def _format_group_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ",".join(f"{group}={count}" for group, count in counts.items())


def _completion_message(
    *,
    out_dir: str,
    document_id: str,
    group_counts: dict[str, int],
    source: str,
    has_raw_extract: bool,
) -> str:
    artifact_status = "raw get_extract captured"
    if not has_raw_extract:
        artifact_status = "diagnostic/final output only (raw get_extract unavailable)"
    return (
        f"run complete. out={out_dir} document_id={document_id} "
        f"groups={_format_group_counts(group_counts)} source={source} {artifact_status}"
    )


def _write_completed_artifacts(
    *,
    gx: GroundX,
    out_dir: str,
    process_id: str,
    document_id: str,
    bl_metadata: typing.Optional[dict],
    rl: RunLog,
    workflow_extract: typing.Optional[dict],
) -> tuple[dict, dict[str, int]]:
    xray_path = _abs(out_dir, "xray.json")
    extract_path = _abs(out_dir, "output.json")
    diagnostic_path = _abs(out_dir, "xray_diagnostic.json")
    reassembly_diagnostic_path = _abs(out_dir, "xray_reassembly_diagnostic.json")
    final_output_path = _abs(out_dir, "final_output.json")

    artifacts = derive_extraction_artifacts(
        gx,
        document_id,
        bl_metadata,
        rl,
        workflow_extract=workflow_extract,
    )
    xray_dict = artifacts["xray"]
    _write_json(xray_path, xray_dict)
    rl.event("xray.captured", path=xray_path, chunks=len(xray_dict.get("chunks") or []))

    output_for_summary = None
    raw_extract = artifacts["raw_extract"]
    diagnostic_extract = artifacts["diagnostic_extract"]
    reassembly_diagnostic = artifacts["reassembly_diagnostic"]
    final_output = artifacts["final_output"]

    if raw_extract is not None:
        _write_json(extract_path, raw_extract)
        _write_output_provenance(out_dir, process_id=process_id, document_id=document_id)
        output_for_summary = raw_extract
        rl.event("extract.captured", path=extract_path, source="get_extract")
    else:
        rl.event("extract.raw_unavailable", output_json_written=False)

    if diagnostic_extract is not None:
        _write_json(diagnostic_path, diagnostic_extract)
        output_for_summary = diagnostic_extract
        rl.event("extract.diagnostic_captured", path=diagnostic_path)

    if reassembly_diagnostic is not None:
        _write_json(reassembly_diagnostic_path, reassembly_diagnostic)
        rl.event(
            "extract.reassembly_diagnostic_captured",
            path=reassembly_diagnostic_path,
        )

    if final_output is not None:
        _write_json(final_output_path, final_output)
        output_for_summary = final_output
        rl.event("extract.final_output_captured", path=final_output_path)

    group_counts = _extract_group_counts(output_for_summary or {})
    rl.event("extract.summary", source=artifacts["source"], group_counts=group_counts)
    return artifacts, group_counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", default=None, help="Path to extraction YAML")
    parser.add_argument("--pdf", default=None, help="Path to PDF to ingest")
    parser.add_argument("--out", required=True, help="Run output directory")
    parser.add_argument("--bucket-name", default=None, help="Bucket name to create")
    parser.add_argument("--workflow-name", default=None, help="Workflow name (default: derived from YAML)")
    parser.add_argument("--reuse-workflow", default=None, help="Existing workflow_id to reuse")
    parser.add_argument("--reuse-bucket", type=int, default=None, help="Existing bucket_id to reuse")
    parser.add_argument("--skip-validate", action="store_true", help="Skip workflow JSON validation")
    parser.add_argument("--add-to-account", action="store_true", help="Set workflow as account default")
    parser.add_argument(
        "--require-raw-extract",
        action="store_true",
        help="Return an error if GroundX get_extract is unavailable; still writes X-Ray diagnostics",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume polling from --out/process_id.txt without compiling, deploying, attaching, or ingesting.",
    )
    parser.add_argument("--poll-interval", type=int, default=15, help="Seconds between status polls")
    parser.add_argument("--max-polls", type=int, default=120, help="Max status polls before timeout")
    parser.add_argument(
        "--allow-high-request-estimate",
        action="store_true",
        help="Proceed even when request-fanout preflight reaches the risk threshold",
    )
    parser.add_argument("--callback-url", default=None, help="Optional callback URL for ingest status updates")
    parser.add_argument("--callback-data", default=None, help="Optional callback data echoed by GroundX callbacks")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    if args.resume:
        process_path = _abs(args.out, "process_id.txt")
        if not os.path.exists(process_path):
            print(
                f"ERROR: --resume requires saved process evidence at {process_path}; "
                "standalone process ID fallback is not supported.",
                file=sys.stderr,
            )
            return 2
    else:
        missing = [
            flag
            for flag, value in (
                ("--yaml", args.yaml),
                ("--pdf", args.pdf),
            )
            if not value
        ]
        if not args.bucket_name and not args.reuse_bucket:
            missing.append("--bucket-name or --reuse-bucket")
        if missing:
            parser.error(
                "the following arguments are required unless --resume is used: "
                + ", ".join(missing)
            )

    workflow_name = args.workflow_name or (
        os.path.splitext(os.path.basename(args.yaml))[0] if args.yaml else "resumed-workflow"
    )
    workflow_json_path = _abs(args.out, "workflow.json")
    diagnostic_path = _abs(args.out, "xray_diagnostic.json")
    final_output_path = _abs(args.out, "final_output.json")

    api_key = os.environ.get("GROUNDX_API_KEY")
    if not api_key:
        print("ERROR: GROUNDX_API_KEY is not set", file=sys.stderr)
        return 2

    gx = GroundX(
        api_key=api_key,
        base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
    )

    with RunLog(_abs(args.out, "run.log")) as rl:
        if args.resume:
            process_id = typing.cast(str, _read_text(_abs(args.out, "process_id.txt")))
            workflow_id = _read_text(_abs(args.out, "workflow_id.txt"))
            bucket_id_text = _read_text(_abs(args.out, "bucket_id.txt"))
            bucket_id: typing.Optional[typing.Union[int, str]]
            if bucket_id_text and bucket_id_text.isdigit():
                bucket_id = int(bucket_id_text)
            else:
                bucket_id = bucket_id_text
            workflow_extract = _load_workflow_extract_from_run(args.out)
            rl.event(
                "run.resume_start",
                out=args.out,
                process_id=process_id,
                workflow_id=workflow_id,
                bucket_id=bucket_id,
            )
            bl_metadata = _load_business_logic_metadata_from_run(args.out, rl)
            document_id = _poll(
                gx,
                process_id,
                args.poll_interval,
                args.max_polls,
                rl,
                out_dir=args.out,
                workflow_id=workflow_id,
                bucket_id=bucket_id,
                started_at=time.time(),
            )
            rl.event("ingest.complete", document_id=document_id)
            if document_id:
                with open(_abs(args.out, "document_id.txt"), "w") as f:
                    f.write(document_id)

            artifacts, group_counts = _write_completed_artifacts(
                gx=gx,
                out_dir=args.out,
                process_id=process_id,
                document_id=document_id,
                bl_metadata=bl_metadata,
                rl=rl,
                workflow_extract=workflow_extract,
            )
            raw_extract = artifacts["raw_extract"]
            diagnostic_extract = artifacts["diagnostic_extract"]
            final_output = artifacts["final_output"]
            if args.require_raw_extract and raw_extract is None:
                rl.event(
                    "extract.required_raw_missing",
                    diagnostic_json=diagnostic_path if diagnostic_extract is not None else None,
                    final_output_json=final_output_path if final_output is not None else None,
                )
                print(
                    "ERROR: GroundX get_extract was unavailable; wrote X-Ray diagnostics instead",
                    file=sys.stderr,
                )
                return 1

            rl.quota_snapshot(gx, label="run.end")
            rl.event("run.done", group_counts=group_counts)
            print(
                _completion_message(
                    out_dir=args.out,
                    document_id=document_id,
                    group_counts=group_counts,
                    source=artifacts["source"],
                    has_raw_extract=raw_extract is not None,
                )
            )
            return 0

        rl.event("run.start", yaml=args.yaml, pdf=args.pdf, out=args.out, bucket_name=args.bucket_name)
        rl.quota_snapshot(gx, label="run.start")

        wf_body: typing.Optional[dict] = None
        workflow_extract: typing.Optional[dict] = None
        if args.reuse_workflow:
            workflow_extract = (
                _load_workflow_extract_from_run(args.out)
                or _load_reused_workflow_extract(gx, args.reuse_workflow)
            )
            if workflow_extract is None:
                report = {
                    "risk_status": "unknown_high_risk",
                    "cap": DEFAULT_CAP,
                    "max_estimated_requests": None,
                    "recommended_action": (
                        "Reused workflow definition could not be loaded for request "
                        "fanout estimation. Load the workflow definition before ingest "
                        "or pass --allow-high-request-estimate to override."
                    ),
                }
                if not _enforce_request_estimate_report(
                    rl,
                    args.out,
                    report,
                    allow_high_request_estimate=args.allow_high_request_estimate,
                ):
                    return 2
            else:
                if not _request_estimate_preflight(
                    rl,
                    args.out,
                    workflow_extract,
                    [args.pdf],
                    allow_high_request_estimate=args.allow_high_request_estimate,
                ):
                    return 2
        else:
            wf_body = _compile(args.yaml, workflow_json_path, workflow_name, rl)
            workflow_extract = wf_body.get("extract")
            if not args.skip_validate:
                _validate(wf_body, workflow_json_path, rl)
            if not _request_estimate_preflight(
                rl,
                args.out,
                wf_body,
                [args.pdf],
                allow_high_request_estimate=args.allow_high_request_estimate,
            ):
                return 2

        # Setup phase — workflow create + bucket create + attach.
        # A workflow created by this setup can be rolled back while it is still
        # unattached. Buckets and post-ingest resources stay in place for
        # review, resume, and explicit cleanup decisions.
        workflow_id: typing.Optional[str] = None
        bucket_id: typing.Optional[int] = None
        created_workflow_id: typing.Optional[str] = None
        created_bucket_id: typing.Optional[int] = None

        try:
            if args.reuse_workflow:
                workflow_id = args.reuse_workflow
                rl.event("workflow.reuse", workflow_id=workflow_id)
                with open(_abs(args.out, "workflow_id.txt"), "w") as f:
                    f.write(workflow_id)
            else:
                assert wf_body is not None
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
                rl.event(
                    "cleanup.bucket.preserved",
                    bucket_id=created_bucket_id,
                    reason="bucket deletion is not a supported harness cleanup path",
                )
            raise

        ingest_resp = gx.ingest(
            documents=[
                Document(
                    bucket_id=bucket_id,
                    file_path=args.pdf,
                    file_name=os.path.basename(args.pdf),
                    file_type="pdf",
                    process_level="full",
                )
            ],
            callback_url=args.callback_url,
            callback_data=args.callback_data,
        )
        process_id = ingest_resp.ingest.process_id
        rl.event(
            "ingest.start",
            process_id=process_id,
            pdf=args.pdf,
            callback_requested=bool(args.callback_url),
            callback_url=_redacted_url(args.callback_url),
            callback_data=args.callback_data,
        )
        with open(_abs(args.out, "process_id.txt"), "w") as f:
            f.write(process_id)

        bl_metadata = _load_business_logic_metadata(args.yaml)
        _write_business_logic_metadata_for_run(args.out, bl_metadata, rl)
        document_id = _poll(
            gx,
            process_id,
            args.poll_interval,
            args.max_polls,
            rl,
            out_dir=args.out,
            workflow_id=workflow_id,
            bucket_id=bucket_id,
            started_at=time.time(),
        )
        rl.event("ingest.complete", document_id=document_id)
        if document_id:
            with open(_abs(args.out, "document_id.txt"), "w") as f:
                f.write(document_id)

        artifacts, group_counts = _write_completed_artifacts(
            gx=gx,
            out_dir=args.out,
            process_id=process_id,
            document_id=document_id,
            bl_metadata=bl_metadata,
            rl=rl,
            workflow_extract=workflow_extract,
        )
        raw_extract = artifacts["raw_extract"]
        diagnostic_extract = artifacts["diagnostic_extract"]
        final_output = artifacts["final_output"]

        if args.require_raw_extract and raw_extract is None:
            rl.event(
                "extract.required_raw_missing",
                diagnostic_json=diagnostic_path if diagnostic_extract is not None else None,
                final_output_json=final_output_path if final_output is not None else None,
            )
            print(
                "ERROR: GroundX get_extract was unavailable; wrote X-Ray diagnostics instead",
                file=sys.stderr,
            )
            return 1

        rl.quota_snapshot(gx, label="run.end")
        rl.event("run.done", group_counts=group_counts)

    print(
        _completion_message(
            out_dir=args.out,
            document_id=document_id,
            group_counts=group_counts,
            source=artifacts["source"],
            has_raw_extract=raw_extract is not None,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
