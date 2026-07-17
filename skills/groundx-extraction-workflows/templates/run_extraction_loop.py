#!/usr/bin/env python3
"""Run a bounded GroundX extraction improvement loop.

This wrapper composes `run_extraction.py` instead of duplicating platform
behavior. Each iteration creates a workflow from the selected YAML, creates or
reuses a bucket, uploads the PDF with `processLevel: full`, polls, requires raw
`documents.get_extract`, scores the raw output, records diffs/artifacts, and
stops at the target accuracy or the iteration cap.

The script does not rewrite prompts by itself. When a run scores below target,
the agent should inspect the PDF, X-Ray, raw output, and score report, then add
the next YAML revision in `--iteration-schema-dir` before continuing.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import time
import typing
from pathlib import Path

import score_extraction as score


DEFAULT_TARGET_ACCURACY = 0.90
DEFAULT_MAX_ITERATIONS = 10


def _write_json(path: Path, payload: typing.Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _read_json(path: Path) -> typing.Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def _overall_accuracy(report: dict) -> float:
    summary = report.get("summary") or {}
    passed = total = 0
    singleton = summary.get("singleton") or (0, 0)
    if isinstance(singleton, (list, tuple)) and len(singleton) == 2:
        passed += int(singleton[0])
        total += int(singleton[1])
    for group_summary in (summary.get("groups") or {}).values():
        fields = (group_summary or {}).get("fields") or (0, 0)
        if isinstance(fields, (list, tuple)) and len(fields) == 2:
            passed += int(fields[0])
            total += int(fields[1])
    return round(passed / total, 4) if total else 0.0


def _raw_provenance_ok(run_dir: Path) -> tuple[bool, str]:
    output_path = run_dir / "output.json"
    provenance_path = run_dir / "output_provenance.json"
    if not output_path.exists():
        return False, "raw output.json missing"
    if not provenance_path.exists():
        return False, "output_provenance.json missing"
    provenance = _read_json(provenance_path)
    process_id = _read_text(run_dir / "process_id.txt")
    document_id = _read_text(run_dir / "document_id.txt")
    if provenance.get("kind") not in (None, "raw_get_extract"):
        return False, "output provenance is not raw get_extract"
    if provenance.get("process_id") != process_id or provenance.get("document_id") != document_id:
        return False, "output provenance does not match process/document"
    return True, "raw get_extract provenance matched"


def score_iteration(run_dir: Path, expected_json: Path) -> dict:
    """Score one iteration's raw output and return report metadata."""
    raw_ok, raw_reason = _raw_provenance_ok(run_dir)
    if not raw_ok:
        report = {
            "has_failure": True,
            "summary": {"singleton": (0, 0), "groups": {}},
            "raw_provenance_error": raw_reason,
        }
    else:
        extracted = _read_json(run_dir / "output.json")
        expected = score.load_answer_key(str(expected_json))
        report = score.compare_extraction(extracted, expected)
    accuracy = _overall_accuracy(report)
    _write_json(run_dir / "accuracy.json", report)
    return {
        "accuracy": accuracy,
        "has_failure": bool(report.get("has_failure")),
        "raw_provenance_ok": raw_ok,
        "raw_provenance_reason": raw_reason,
        "report_path": str(run_dir / "accuracy.json"),
    }


def _schema_candidates(base_yaml: Path, iteration_schema_dir: Path, iteration: int) -> list[Path]:
    return [
        iteration_schema_dir / f"{base_yaml.stem}.iteration-{iteration:02d}.yaml",
        iteration_schema_dir / f"iteration-{iteration:02d}.yaml",
    ]


def schema_for_iteration(base_yaml: Path, iteration_schema_dir: str | None, iteration: int) -> Path | None:
    if iteration == 1:
        return base_yaml
    if not iteration_schema_dir:
        return None
    schema_dir = Path(iteration_schema_dir)
    for candidate in _schema_candidates(base_yaml, schema_dir, iteration):
        if candidate.exists():
            return candidate
    return None


def write_diff(previous: Path | None, current: Path, out_path: Path) -> str | None:
    if previous is None or not previous.exists() or not current.exists():
        return None
    before = previous.read_text(encoding="utf-8").splitlines(keepends=True)
    after = current.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=str(previous),
            tofile=str(current),
        )
    )
    out_path.write_text(diff, encoding="utf-8")
    return str(out_path)


def build_run_command(args: argparse.Namespace, schema_path: Path, run_dir: Path, iteration: int) -> list[str]:
    runner = Path(__file__).with_name("run_extraction.py")
    command = [
        sys.executable,
        str(runner),
        "--yaml",
        str(schema_path),
        "--pdf",
        args.pdf,
        "--out",
        str(run_dir),
        "--workflow-name",
        f"{args.workflow_name_prefix}-{iteration:02d}",
        "--poll-interval",
        str(args.poll_interval),
        "--max-polls",
        str(args.max_polls),
        "--require-raw-extract",
    ]
    if args.reuse_bucket:
        command.extend(["--reuse-bucket", str(args.reuse_bucket)])
    else:
        command.extend(["--bucket-name", f"{args.bucket_name_prefix}-{int(time.time())}-{iteration:02d}"])
    if args.allow_high_request_estimate:
        command.append("--allow-high-request-estimate")
    if args.callback_url:
        command.extend(
            [
                "--callback-url",
                args.callback_url,
                "--callback-data",
                f"{args.callback_data_prefix}:{iteration:02d}",
            ]
        )
    return command


def summarize_iteration(run_dir: Path, iteration: int, schema_path: Path, command: list[str], result: subprocess.CompletedProcess, score_summary: dict, diff_path: str | None) -> dict:
    return {
        "iteration": iteration,
        "schema_path": str(schema_path),
        "run_dir": str(run_dir),
        "command": command,
        "returncode": result.returncode,
        "workflow_id": _read_text(run_dir / "workflow_id.txt"),
        "bucket_id": _read_text(run_dir / "bucket_id.txt"),
        "process_id": _read_text(run_dir / "process_id.txt"),
        "document_id": _read_text(run_dir / "document_id.txt"),
        "raw_extraction_path": str(run_dir / "output.json") if (run_dir / "output.json").exists() else None,
        "raw_provenance_path": str(run_dir / "output_provenance.json") if (run_dir / "output_provenance.json").exists() else None,
        "xray_path": str(run_dir / "xray.json") if (run_dir / "xray.json").exists() else None,
        "request_fanout_path": str(run_dir / "request_estimate.json") if (run_dir / "request_estimate.json").exists() else None,
        "score": score_summary,
        "yaml_diff_path": diff_path,
    }


def run_loop(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_yaml = Path(args.yaml)
    expected_json = Path(args.expected_json)
    iterations: list[dict] = []
    previous_schema: Path | None = None
    status = "failed"
    best_accuracy = 0.0

    for iteration in range(1, args.max_iterations + 1):
        schema_path = schema_for_iteration(base_yaml, args.iteration_schema_dir, iteration)
        if schema_path is None:
            status = "blocked"
            iterations.append({
                "iteration": iteration,
                "status": "blocked",
                "reason": "no next YAML revision available before target accuracy",
            })
            break

        run_dir = out_dir / f"iteration-{iteration:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        diff_path = write_diff(previous_schema, schema_path, run_dir / "schema.diff")
        command = build_run_command(args, schema_path, run_dir, iteration)
        started = time.monotonic()
        result = subprocess.run(command, cwd=Path(__file__).parent, text=True, capture_output=True)
        duration = round(time.monotonic() - started, 3)
        (run_dir / "loop.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (run_dir / "loop.stderr.txt").write_text(result.stderr, encoding="utf-8")
        score_summary = score_iteration(run_dir, expected_json)
        score_summary["duration_seconds"] = duration
        iteration_summary = summarize_iteration(
            run_dir,
            iteration,
            schema_path,
            command,
            result,
            score_summary,
            diff_path,
        )
        iteration_summary["status"] = (
            "passed"
            if result.returncode == 0
            and score_summary["raw_provenance_ok"]
            and not score_summary["has_failure"]
            and score_summary["accuracy"] >= args.target_accuracy
            else "failed"
        )
        iterations.append(iteration_summary)
        best_accuracy = max(best_accuracy, float(score_summary["accuracy"]))
        _write_json(out_dir / "loop_state.json", {
            "status": "running",
            "target_accuracy": args.target_accuracy,
            "max_iterations": args.max_iterations,
            "best_accuracy": round(best_accuracy, 4),
            "iterations": iterations,
        })

        if iteration_summary["status"] == "passed":
            status = "passed"
            break
        previous_schema = schema_path

    final_report = {
        "status": status,
        "target_accuracy": args.target_accuracy,
        "max_iterations": args.max_iterations,
        "best_accuracy": round(best_accuracy, 4),
        "iterations": iterations,
    }
    _write_json(out_dir / "final_report.json", final_report)
    _write_json(out_dir / "loop_state.json", final_report)
    return final_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", required=True, help="Initial extraction YAML")
    parser.add_argument("--pdf", required=True, help="PDF to process")
    parser.add_argument("--expected-json", required=True, help="Runner-shaped expected-answer JSON")
    parser.add_argument("--out", required=True, help="Loop output directory")
    parser.add_argument("--iteration-schema-dir", default=None, help="Optional dir with iteration-02 YAML revisions")
    parser.add_argument("--target-accuracy", type=float, default=DEFAULT_TARGET_ACCURACY)
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--bucket-name-prefix", default="extract-loop", help="Prefix when creating per-iteration buckets")
    parser.add_argument("--reuse-bucket", type=int, default=None, help="Existing bucket ID to attach each iteration workflow to")
    parser.add_argument("--workflow-name-prefix", default="extract-loop")
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--max-polls", type=int, default=120)
    parser.add_argument("--allow-high-request-estimate", action="store_true")
    parser.add_argument("--callback-url", default=None)
    parser.add_argument("--callback-data-prefix", default="extract-loop")
    args = parser.parse_args()

    if args.max_iterations < 1 or args.max_iterations > DEFAULT_MAX_ITERATIONS:
        parser.error("--max-iterations must be between 1 and 10")
    if args.target_accuracy <= 0 or args.target_accuracy > 1:
        parser.error("--target-accuracy must be > 0 and <= 1")

    report = run_loop(args)
    print(
        f"loop {report['status']}: best_accuracy={report['best_accuracy']:.0%} "
        f"iterations={len(report['iterations'])} -> {Path(args.out) / 'final_report.json'}"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
