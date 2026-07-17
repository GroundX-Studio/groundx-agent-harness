"""Offline tests for the bounded extraction loop runner."""

import json
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_extraction_loop  # noqa: E402


def _args(tmp_path, **overrides):
    base = {
        "yaml": str(tmp_path / "prompt.yaml"),
        "pdf": str(tmp_path / "sample.pdf"),
        "expected_json": str(tmp_path / "expected.json"),
        "out": str(tmp_path / "loop"),
        "iteration_schema_dir": None,
        "target_accuracy": 0.9,
        "max_iterations": 10,
        "bucket_name_prefix": "loop-bucket",
        "reuse_bucket": None,
        "workflow_name_prefix": "loop-workflow",
        "poll_interval": 0,
        "max_polls": 1,
        "allow_high_request_estimate": False,
        "callback_url": None,
        "callback_data_prefix": "loop",
    }
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _write_inputs(tmp_path):
    (tmp_path / "prompt.yaml").write_text("statement:\n  fields: {}\n")
    (tmp_path / "sample.pdf").write_bytes(b"%PDF")
    (tmp_path / "expected.json").write_text(json.dumps({"statement": {"account_number": "A-1"}}))


def test_loop_stops_after_first_iteration_at_target_accuracy(tmp_path, monkeypatch):
    _write_inputs(tmp_path)

    def fake_run(command, cwd, text, capture_output):
        run_dir = Path(command[command.index("--out") + 1])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "workflow_id.txt").write_text("workflow-1")
        (run_dir / "bucket_id.txt").write_text("101")
        (run_dir / "process_id.txt").write_text("process-1")
        (run_dir / "document_id.txt").write_text("document-1")
        (run_dir / "request_estimate.json").write_text(json.dumps({"risk_status": "ok"}))
        (run_dir / "output.json").write_text(json.dumps({"statement": {"account_number": "A-1"}}))
        (run_dir / "output_provenance.json").write_text(
            json.dumps(
                {
                    "kind": "raw_get_extract",
                    "process_id": "process-1",
                    "document_id": "document-1",
                }
            )
        )
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(run_extraction_loop.subprocess, "run", fake_run)

    report = run_extraction_loop.run_loop(_args(tmp_path))

    assert report["status"] == "passed"
    assert report["best_accuracy"] == 1.0
    assert len(report["iterations"]) == 1
    command = report["iterations"][0]["command"]
    assert "--require-raw-extract" in command
    assert "--bucket-name" in command
    assert json.loads((tmp_path / "loop" / "final_report.json").read_text())["status"] == "passed"


def test_loop_blocks_without_next_yaml_revision(tmp_path, monkeypatch):
    _write_inputs(tmp_path)

    def fake_run(command, cwd, text, capture_output):
        run_dir = Path(command[command.index("--out") + 1])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "process_id.txt").write_text("process-1")
        (run_dir / "document_id.txt").write_text("document-1")
        (run_dir / "output.json").write_text(json.dumps({"statement": {"account_number": "WRONG"}}))
        (run_dir / "output_provenance.json").write_text(
            json.dumps(
                {
                    "kind": "raw_get_extract",
                    "process_id": "process-1",
                    "document_id": "document-1",
                }
            )
        )
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(run_extraction_loop.subprocess, "run", fake_run)

    report = run_extraction_loop.run_loop(_args(tmp_path, max_iterations=2))

    assert report["status"] == "blocked"
    assert report["iterations"][0]["status"] == "failed"
    assert report["iterations"][1]["status"] == "blocked"
    assert report["best_accuracy"] == 0.0


def test_build_command_can_reuse_existing_bucket(tmp_path):
    _write_inputs(tmp_path)
    args = _args(tmp_path, reuse_bucket=123)

    command = run_extraction_loop.build_run_command(args, tmp_path / "prompt.yaml", tmp_path / "run", 1)

    assert "--reuse-bucket" in command
    assert command[command.index("--reuse-bucket") + 1] == "123"
    assert "--bucket-name" not in command
