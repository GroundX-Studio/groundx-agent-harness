"""Tests for the live extraction runner helpers.

These tests use fake SDK clients so they stay offline. They guard the runner
contracts that matter for user-facing live runs: failed document progress must
not be reported as success, and raw GroundX extract artifacts must stay separate
from local X-Ray diagnostics.
"""

import os
import sys
import types
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if "groundx" not in sys.modules:
    groundx_stub = types.ModuleType("groundx")
    groundx_stub.Document = object
    groundx_stub.GroundX = object
    sys.modules["groundx"] = groundx_stub

import run_extraction  # noqa: E402


class RecordingLog:
    def __init__(self):
        self.events = []

    def event(self, name, **kwargs):
        self.events.append({"event": name, **kwargs})


def ns(**kwargs):
    return types.SimpleNamespace(**kwargs)


class ExplodingWorkflows:
    def create(self, **kwargs):
        raise AssertionError("resume must not create workflows")

    def add_to_id(self, **kwargs):
        raise AssertionError("resume must not attach workflows")

    def add_to_account(self, **kwargs):
        raise AssertionError("resume must not mutate account defaults")


class ExplodingBuckets:
    def create(self, **kwargs):
        raise AssertionError("resume must not create buckets")


class ResumeGroundX:
    def __init__(self, **kwargs):
        self.workflows = ExplodingWorkflows()
        self.buckets = ExplodingBuckets()
        self.documents = ns(
            get_processing_status_by_id=self.get_processing_status_by_id,
            get_xray=lambda document_id: {"chunks": []},
            get_extract=lambda document_id: {"statement": {"account_number": "A-1"}},
        )

    def ingest(self, **kwargs):
        raise AssertionError("resume must not ingest documents")

    def get_processing_status_by_id(self, process_id):
        assert process_id == "process-1"
        return ns(
            ingest=ns(
                status="complete",
                progress=ns(
                    complete=ns(documents=[ns(document_id="doc-1")]),
                    processing=ns(documents=[]),
                    errors=ns(total=0, documents=[]),
                ),
            )
        )


class ResumeNoRawGroundX(ResumeGroundX):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.documents.get_extract = lambda document_id: {}
        self.documents.get_xray = lambda document_id: {
            "chunks": [
                {
                    "customChunkOutputs": {
                        "statement_fields": {"account_number": "A-1"}
                    }
                }
            ]
        }


class ResumeNoRawChargesGroundX(ResumeGroundX):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.documents.get_extract = lambda document_id: {}
        self.documents.get_xray = lambda document_id: {
            "chunks": [
                {
                    "customChunkOutputs": {
                        "charge_fields": [
                            {"description": "Service fee", "amount": "10.00"},
                            {"description": "Service fee", "amount": "10.00"},
                        ]
                    }
                }
            ]
        }


class ResumeErrorGroundX(ResumeGroundX):
    def get_processing_status_by_id(self, process_id):
        assert process_id == "process-1"
        return ns(
            ingest=ns(
                status="complete",
                progress=ns(
                    complete=ns(documents=[]),
                    processing=ns(documents=[]),
                    errors=ns(
                        documents=[
                            ns(
                                document_id="doc-1",
                                status_message="file too large for this subscription",
                            )
                        ]
                    ),
                ),
            )
        )


class FreshNoRawGroundX(ResumeNoRawGroundX):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workflows = ns(add_to_id=lambda **kwargs: ns(ok=True))
        self.buckets = ns(create=lambda **kwargs: ns(bucket=ns(bucket_id=101)))

    def ingest(self, **kwargs):
        return ns(ingest=ns(process_id="process-1"))


def test_poll_fails_when_progress_errors_exist_even_if_status_is_complete():
    rl = RecordingLog()
    status = ns(
        ingest=ns(
            status="complete",
            progress=ns(
                complete=ns(documents=[]),
                processing=ns(documents=[]),
                errors=ns(
                    documents=[
                        ns(
                            document_id="doc-1",
                            status_message="file is too large to process for this subscription level",
                        )
                    ]
                ),
            ),
        )
    )
    gx = ns(
        documents=ns(
            get_processing_status_by_id=lambda process_id: status,
        )
    )

    with pytest.raises(SystemExit, match="document errors"):
        run_extraction._poll(gx, "process-1", interval=0, max_polls=1, rl=rl)

    assert any(event["event"] == "ingest.failed" for event in rl.events)


def test_poll_fails_when_progress_errors_total_is_nonzero_without_documents():
    rl = RecordingLog()
    status = ns(
        ingest=ns(
            status="complete",
            progress=ns(
                complete=ns(documents=[ns(document_id="doc-1")]),
                processing=ns(documents=[]),
                errors=ns(total=1, documents=[]),
            ),
        )
    )
    gx = ns(
        documents=ns(
            get_processing_status_by_id=lambda process_id: status,
        )
    )

    with pytest.raises(SystemExit, match="1 document error"):
        run_extraction._poll(gx, "process-1", interval=0, max_polls=1, rl=rl)

    assert any(event["event"] == "ingest.failed" for event in rl.events)


def test_poll_fails_when_complete_status_has_no_document_id():
    rl = RecordingLog()
    status = ns(
        ingest=ns(
            status="complete",
            progress=ns(
                complete=ns(documents=[]),
                processing=ns(documents=[]),
                errors=ns(documents=[]),
            ),
        )
    )
    gx = ns(
        documents=ns(
            get_processing_status_by_id=lambda process_id: status,
        )
    )

    with pytest.raises(SystemExit, match="no completed document ID"):
        run_extraction._poll(gx, "process-1", interval=0, max_polls=1, rl=rl)

    assert any(event["event"] == "ingest.failed" for event in rl.events)


def test_poll_timeout_writes_actionable_summary_and_bounded_history(tmp_path):
    rl = RecordingLog()
    history_path = tmp_path / "timeout_history.json"
    history_path.write_text(json.dumps([{"attempt": i} for i in range(12)]))
    (tmp_path / "output.json").write_text('{"old": true}')
    (tmp_path / "output_provenance.json").write_text(
        json.dumps({"process_id": "old-process", "document_id": "old-doc", "artifact": "output.json"})
    )
    status = ns(
        ingest=ns(
            status="processing",
            progress=ns(
                complete=ns(total=0, documents=[]),
                processing=ns(total=1, documents=[ns(document_id="doc-1")]),
                errors=ns(total=0, documents=[]),
            ),
        )
    )
    gx = ns(documents=ns(get_processing_status_by_id=lambda process_id: status))

    with pytest.raises(SystemExit) as excinfo:
        run_extraction._poll(
            gx,
            "process-1",
            interval=0,
            max_polls=1,
            rl=rl,
            out_dir=str(tmp_path),
            workflow_id="workflow-1",
            bucket_id=101,
            started_at=1000.0,
            now_fn=lambda: 1012.5,
        )

    message = str(excinfo.value)
    assert "platform process may still be running" in message
    assert "resume polling the same process" in message

    summary = json.loads((tmp_path / "timeout_summary.json").read_text())
    history = json.loads(history_path.read_text())
    assert summary["process_id"] == "process-1"
    assert summary["workflow_id"] == "workflow-1"
    assert summary["bucket_id"] == 101
    assert summary["elapsed_seconds"] == 12.5
    assert summary["poll_count"] == 1
    assert summary["last_status"] == "processing"
    assert summary["progress_counts"] == {"complete": 0, "processing": 1, "errors": 0}
    assert summary["output_json_exists"] is True
    assert summary["scoreable"] is False
    assert summary["scoreability_reason"] == "raw output provenance does not match this process"
    assert summary["resume_command"].endswith(f"--resume --out {tmp_path}")
    assert len(history) == 10
    assert history[-1] == summary
    assert any(event["event"] == "ingest.timeout" for event in rl.events)


def test_resume_requires_saved_process_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["run_extraction.py", "--resume", "--out", str(tmp_path)])

    rc = run_extraction.main()

    captured = capsys.readouterr()
    assert rc == 2
    assert "process_id.txt" in captured.err
    assert "standalone process ID" in captured.err


def test_resume_does_not_compile_deploy_attach_or_ingest(tmp_path, monkeypatch):
    (tmp_path / "process_id.txt").write_text("process-1")
    (tmp_path / "workflow_id.txt").write_text("workflow-1")
    (tmp_path / "bucket_id.txt").write_text("101")
    (tmp_path / "workflow.json").write_text(json.dumps({"extract": {"outputRoutes": []}}))

    def forbidden(*args, **kwargs):
        raise AssertionError("resume must not run setup helpers")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", ResumeGroundX)
    monkeypatch.setattr(run_extraction, "_compile", forbidden)
    monkeypatch.setattr(run_extraction, "_validate", forbidden)
    monkeypatch.setattr(run_extraction, "_create_workflow", forbidden)
    monkeypatch.setattr(run_extraction, "_load_business_logic_metadata", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--resume",
            "--out",
            str(tmp_path),
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    rc = run_extraction.main()

    assert rc == 0
    assert (tmp_path / "document_id.txt").read_text() == "doc-1"
    assert json.loads((tmp_path / "output.json").read_text()) == {
        "statement": {"account_number": "A-1"}
    }
    provenance = json.loads((tmp_path / "output_provenance.json").read_text())
    assert provenance["process_id"] == "process-1"
    assert provenance["document_id"] == "doc-1"
    run_events = [
        json.loads(line)
        for line in (tmp_path / "run.log").read_text().splitlines()
    ]
    resume_start = next(event for event in run_events if event["event"] == "run.resume_start")
    assert resume_start["process_id"] == "process-1"
    assert resume_start["workflow_id"] == "workflow-1"
    assert resume_start["bucket_id"] == 101


def test_fresh_run_persists_business_logic_metadata_for_resume(tmp_path, monkeypatch):
    metadata = {"charges": {"unique_attrs": ["description"]}}

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", FreshNoRawGroundX)
    monkeypatch.setattr(run_extraction, "Document", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        run_extraction,
        "_compile",
        lambda *args, **kwargs: {
            "name": "workflow-name",
            "extract": {"workflow": {"output_routes": []}},
        },
    )
    monkeypatch.setattr(run_extraction, "_validate", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        run_extraction,
        "_create_workflow",
        lambda *args, **kwargs: ns(workflow=ns(workflow_id="workflow-1")),
    )
    monkeypatch.setattr(
        run_extraction,
        "_load_business_logic_metadata",
        lambda yaml_path: metadata,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--yaml",
            "prompt.yaml",
            "--pdf",
            "sample.pdf",
            "--out",
            str(tmp_path),
            "--bucket-name",
            "bucket",
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    rc = run_extraction.main()

    assert rc == 0
    assert json.loads((tmp_path / "business_logic_metadata.json").read_text()) == metadata


def test_fresh_run_persists_business_logic_metadata_before_poll_timeout(tmp_path, monkeypatch):
    metadata = {"charges": {"unique_attrs": ["description"]}}

    def timeout_after_checking_metadata(*args, **kwargs):
        metadata_path = tmp_path / "business_logic_metadata.json"
        assert metadata_path.exists(), "business logic metadata must be durable before polling can time out"
        assert json.loads(metadata_path.read_text()) == metadata
        raise SystemExit("ingest timed out")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", FreshNoRawGroundX)
    monkeypatch.setattr(run_extraction, "Document", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        run_extraction,
        "_compile",
        lambda *args, **kwargs: {
            "name": "workflow-name",
            "extract": {"workflow": {"output_routes": []}},
        },
    )
    monkeypatch.setattr(run_extraction, "_validate", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        run_extraction,
        "_create_workflow",
        lambda *args, **kwargs: ns(workflow=ns(workflow_id="workflow-1")),
    )
    monkeypatch.setattr(
        run_extraction,
        "_load_business_logic_metadata",
        lambda yaml_path: metadata,
    )
    monkeypatch.setattr(run_extraction, "_poll", timeout_after_checking_metadata)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--yaml",
            "prompt.yaml",
            "--pdf",
            "sample.pdf",
            "--out",
            str(tmp_path),
            "--bucket-name",
            "bucket",
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    with pytest.raises(SystemExit, match="ingest timed out"):
        run_extraction.main()


def test_resume_writes_diagnostic_and_final_artifacts_when_raw_extract_is_unavailable(tmp_path, monkeypatch):
    (tmp_path / "process_id.txt").write_text("process-1")
    (tmp_path / "workflow_id.txt").write_text("workflow-1")
    (tmp_path / "bucket_id.txt").write_text("101")
    (tmp_path / "workflow.json").write_text(
        json.dumps(
            {
                "extract": {
                    "workflow": {
                        "output_routes": [
                            {
                                "workflow_group": "statement",
                                "workflow_field": "account_number",
                                "final_path": "/statement/account_number",
                                "step_name": "statement_fields",
                                "level": "chunk",
                                "output_map": "customChunkOutputs",
                                "output_key": "account_number",
                            }
                        ]
                    }
                }
            }
        )
    )

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", ResumeNoRawGroundX)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--resume",
            "--out",
            str(tmp_path),
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    rc = run_extraction.main()

    assert rc == 0
    assert (tmp_path / "document_id.txt").read_text() == "doc-1"
    assert (tmp_path / "xray.json").exists()
    assert not (tmp_path / "output.json").exists()
    assert json.loads((tmp_path / "xray_diagnostic.json").read_text()) == {
        "statement": {"account_number": "A-1"}
    }
    assert json.loads((tmp_path / "final_output.json").read_text()) == {
        "statement": {"account_number": "A-1"}
    }


def test_resume_applies_persisted_business_logic_metadata_to_diagnostic_output(tmp_path, monkeypatch):
    (tmp_path / "process_id.txt").write_text("process-1")
    (tmp_path / "workflow_id.txt").write_text("workflow-1")
    (tmp_path / "bucket_id.txt").write_text("101")
    (tmp_path / "business_logic_metadata.json").write_text(
        json.dumps({"charges": {"unique_attrs": ["description"]}})
    )
    (tmp_path / "workflow.json").write_text(
        json.dumps(
            {
                "extract": {
                    "workflow": {
                        "custom_steps": [{"name": "charge_fields", "kind": "keys"}],
                        "output_routes": [
                            {
                                "workflow_group": "charges",
                                "workflow_field": "description",
                                "final_path": "/charges/*/description",
                                "step_name": "charge_fields",
                                "level": "chunk",
                                "output_map": "customChunkOutputs",
                                "output_key": "description",
                            },
                            {
                                "workflow_group": "charges",
                                "workflow_field": "amount",
                                "final_path": "/charges/*/amount",
                                "step_name": "charge_fields",
                                "level": "chunk",
                                "output_map": "customChunkOutputs",
                                "output_key": "amount",
                            },
                        ],
                    }
                }
            }
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("resume must not reload business logic from YAML")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", ResumeNoRawChargesGroundX)
    monkeypatch.setattr(run_extraction, "_load_business_logic_metadata", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--resume",
            "--out",
            str(tmp_path),
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    rc = run_extraction.main()

    assert rc == 0
    assert json.loads((tmp_path / "xray_diagnostic.json").read_text()) == {
        "charges": [
            {"description": "Service fee", "amount": "10.00"},
            {"description": "Service fee", "amount": "10.00"},
        ]
    }
    assert json.loads((tmp_path / "final_output.json").read_text()) == {
        "charges": [{"description": "Service fee", "amount": "10.00"}]
    }


def test_resume_nested_progress_errors_fail_before_scoring(tmp_path, monkeypatch):
    (tmp_path / "process_id.txt").write_text("process-1")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", ResumeErrorGroundX)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--resume",
            "--out",
            str(tmp_path),
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    with pytest.raises(SystemExit, match="document errors"):
        run_extraction.main()

    assert not (tmp_path / "output.json").exists()
    assert not (tmp_path / "xray_diagnostic.json").exists()
    run_events = [
        json.loads(line)
        for line in (tmp_path / "run.log").read_text().splitlines()
    ]
    assert any(event["event"] == "ingest.failed" for event in run_events)


def test_extract_artifacts_trusts_section_shaped_get_extract_output():
    rl = RecordingLog()
    raw_extract = {
        "plan_information": {
            "plan_name": "401k plan",
            "plan_number": "123",
        }
    }
    gx = ns(
        documents=ns(
            get_xray=lambda document_id: {"chunks": []},
            get_extract=lambda document_id: raw_extract,
        )
    )

    artifacts = run_extraction.derive_extraction_artifacts(gx, "doc-1", rl=rl)

    assert artifacts["raw_extract"] == raw_extract
    assert artifacts["diagnostic_extract"] is None
    assert artifacts["final_output"] is None
    assert artifacts["source"] == "get_extract"


def test_extract_artifacts_treats_empty_get_extract_dict_as_raw_unavailable():
    rl = RecordingLog()
    gx = ns(
        documents=ns(
            get_xray=lambda document_id: {"chunks": [{"sectionSummary": '{"fallback": "value"}'}]},
            get_extract=lambda document_id: {},
        )
    )

    artifacts = run_extraction.derive_extraction_artifacts(gx, "doc-1", rl=rl)

    assert artifacts["raw_extract"] is None
    assert artifacts["diagnostic_extract"]["fallback"] == "value"
    assert artifacts["final_output"]["fallback"] == "value"
    assert artifacts["source"] == "xray_to_extract"
    assert any(event["event"] == "extract.get_extract_empty" for event in rl.events)


def test_extract_artifacts_keeps_non_empty_raw_extract_even_when_values_are_empty():
    rl = RecordingLog()
    raw_extract = {
        "statement": {"optional_note": ""},
        "charges": [],
    }
    gx = ns(
        documents=ns(
            get_xray=lambda document_id: {"chunks": [{"sectionSummary": '{"fallback": "value"}'}]},
            get_extract=lambda document_id: raw_extract,
        )
    )

    artifacts = run_extraction.derive_extraction_artifacts(gx, "doc-1", rl=rl)

    assert artifacts["raw_extract"] == raw_extract
    assert artifacts["diagnostic_extract"] is None
    assert artifacts["final_output"] is None
    assert artifacts["source"] == "get_extract"
    assert not any(event["event"] == "extract.get_extract_empty" for event in rl.events)


def test_extract_artifacts_writes_diagnostic_separately_when_raw_extract_404s(monkeypatch):
    rl = RecordingLog()
    xray = {
        "chunks": [
            {
                "sectionSummary": '{"account_number": "A-1"}',
            }
        ]
    }
    gx = ns(
        documents=ns(
            get_xray=lambda document_id: xray,
            get_extract=lambda document_id: (_ for _ in ()).throw(RuntimeError("404 not found")),
        )
    )

    artifacts = run_extraction.derive_extraction_artifacts(gx, "doc-1", rl=rl)

    assert artifacts["raw_extract"] is None
    assert artifacts["diagnostic_extract"]["account_number"] == "A-1"
    assert artifacts["final_output"]["account_number"] == "A-1"
    assert artifacts["source"] == "xray_to_extract"
    assert any(event["event"] == "extract.get_extract_unavailable" for event in rl.events)


def test_completion_message_names_diagnostic_source_when_raw_missing():
    message = run_extraction._completion_message(
        out_dir="run",
        document_id="doc-1",
        group_counts={"account_number": 1},
        source="xray_to_extract",
        has_raw_extract=False,
    )

    assert "diagnostic/final output only" in message
    assert "raw get_extract unavailable" in message
