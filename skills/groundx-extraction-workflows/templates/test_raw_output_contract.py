"""Regression coverage for the live raw-output boundary.

Run directly:
    python -m pytest templates/test_raw_output_contract.py -q
"""

import ast
import json
import os
from pathlib import Path
import sys
import types

from pypdf import PdfWriter


TEMPLATES = Path(__file__).resolve().parent
if str(TEMPLATES) not in sys.path:
    sys.path.insert(0, str(TEMPLATES))

import batch_extraction  # noqa: E402
import run_extraction  # noqa: E402


def ns(**kwargs):
    return types.SimpleNamespace(**kwargs)


RAW_EXTRACT = {
    "charges": [
        {"code": "service", "amount": "10.00"},
        {"code": "service", "amount": "12.00"},
    ]
}
BUSINESS_LOGIC_YAML = """
charges:
  unique_attrs: [code]
  fields:
    code:
      type: string
    amount:
      type: number
workflow:
  custom_steps: []
"""


class _LiveGroundX:
    def __init__(self, **kwargs):
        self.workflows = ns(
            validate=lambda **kwargs: ns(),
            create=lambda **kwargs: ns(workflow=ns(workflow_id="workflow-1")),
            add_to_id=lambda **kwargs: ns(),
            delete=lambda **kwargs: ns(),
        )
        self.buckets = ns(create=lambda **kwargs: ns(bucket=ns(bucket_id=101)))
        self.documents = ns(
            get_processing_status_by_id=self._status,
            get_xray=lambda **kwargs: {"chunks": []},
            get_extract=lambda **kwargs: RAW_EXTRACT,
        )

    def ingest(self, **kwargs):
        return ns(ingest=ns(process_id="process-1"))

    def _status(self, **kwargs):
        return ns(
            ingest=ns(
                status="complete",
                progress=ns(
                    complete=ns(documents=[ns(document_id="document-1")]),
                    processing=ns(documents=[]),
                    errors=ns(total=0, documents=[]),
                ),
            )
        )


def _write_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)


def _run_fresh(tmp_path: Path, monkeypatch) -> int:
    yaml_path = tmp_path / "prompt.yaml"
    pdf_path = tmp_path / "document.pdf"
    yaml_path.write_text(BUSINESS_LOGIC_YAML, encoding="utf-8")
    _write_pdf(pdf_path)

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", _LiveGroundX)
    monkeypatch.setattr(run_extraction, "Document", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_extraction.py",
            "--yaml",
            str(yaml_path),
            "--pdf",
            str(pdf_path),
            "--out",
            str(tmp_path),
            "--bucket-name",
            "raw-output-contract",
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )
    return run_extraction.main()


def test_fresh_run_with_dedupe_metadata_writes_only_raw_server_output(tmp_path, monkeypatch):
    """Fresh live runs must not create local metadata or transformed output."""
    assert _run_fresh(tmp_path, monkeypatch) == 0

    assert json.loads((tmp_path / "output.json").read_text()) == RAW_EXTRACT
    assert len(json.loads((tmp_path / "output.json").read_text())["charges"]) == 2
    assert not (tmp_path / "business_logic_metadata.json").exists()
    assert not (tmp_path / "final_output.json").exists()


def test_resumed_run_ignores_business_logic_sidecars(tmp_path, monkeypatch):
    """Resume continues saved process state without reading local output metadata."""
    (tmp_path / "process_id.txt").write_text("process-1", encoding="utf-8")
    (tmp_path / "workflow_id.txt").write_text("workflow-1", encoding="utf-8")
    (tmp_path / "bucket_id.txt").write_text("101", encoding="utf-8")
    sidecar = tmp_path / "business_logic_metadata.json"
    invalid_sidecar = '{"charges": {"unique_attrs": 42}}\n'
    sidecar.write_text(invalid_sidecar, encoding="utf-8")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(run_extraction, "GroundX", _LiveGroundX)
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

    try:
        result = run_extraction.main()
    except TypeError:
        result = None

    assert result == 0

    events = [json.loads(line) for line in (tmp_path / "run.log").read_text().splitlines()]
    assert json.loads((tmp_path / "output.json").read_text()) == RAW_EXTRACT
    assert not any(event["event"].startswith("business_logic.") for event in events)
    assert sidecar.read_text(encoding="utf-8") == invalid_sidecar
    assert not (tmp_path / "final_output.json").exists()


def test_batch_writes_and_scores_raw_extract_without_final_artifact(tmp_path, monkeypatch):
    """Batch scoring must consume the raw server artifact, never a local final output."""
    docs_dir = tmp_path / "docs"
    keys_dir = tmp_path / "keys"
    docs_dir.mkdir()
    keys_dir.mkdir()
    yaml_path = tmp_path / "prompt.yaml"
    document_path = docs_dir / "statement.pdf"
    yaml_path.write_text(BUSINESS_LOGIC_YAML, encoding="utf-8")
    _write_pdf(document_path)
    (keys_dir / "statement.json").write_text(json.dumps(RAW_EXTRACT), encoding="utf-8")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(batch_extraction, "GroundX", _LiveGroundX)
    monkeypatch.setattr(batch_extraction, "Document", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "batch_extraction.py",
            "--yaml",
            str(yaml_path),
            "--docs-dir",
            str(docs_dir),
            "--keys-dir",
            str(keys_dir),
            "--out",
            str(tmp_path / "out"),
            "--bucket-name",
            "raw-output-contract",
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    assert batch_extraction.main() == 0

    out_dir = tmp_path / "out"
    events = [json.loads(line) for line in (out_dir / "verify.log").read_text().splitlines()]
    assert json.loads((out_dir / "statement.extracted.json").read_text()) == RAW_EXTRACT
    assert not (out_dir / "statement.final_output.json").exists()
    assert any(
        event["event"] == "verify.doc.done" and event["score_source"] == "raw"
        for event in events
    )


def test_batch_never_scores_legacy_final_output_when_raw_extract_is_missing(
    tmp_path, monkeypatch
):
    """Raw-unavailable batch runs must stay partial instead of scoring a legacy final."""
    docs_dir = tmp_path / "docs"
    keys_dir = tmp_path / "keys"
    docs_dir.mkdir()
    keys_dir.mkdir()
    yaml_path = tmp_path / "prompt.yaml"
    document_path = docs_dir / "statement.pdf"
    yaml_path.write_text(BUSINESS_LOGIC_YAML, encoding="utf-8")
    _write_pdf(document_path)
    (keys_dir / "statement.json").write_text(json.dumps(RAW_EXTRACT), encoding="utf-8")

    monkeypatch.setenv("GROUNDX_API_KEY", "test-key")
    monkeypatch.setattr(batch_extraction, "GroundX", _LiveGroundX)
    monkeypatch.setattr(batch_extraction, "Document", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        batch_extraction,
        "derive_extraction_artifacts",
        lambda *args, **kwargs: {
            "raw_extract": None,
            "xray": {"chunks": []},
            "source": "get_extract_unavailable",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "batch_extraction.py",
            "--yaml",
            str(yaml_path),
            "--docs-dir",
            str(docs_dir),
            "--keys-dir",
            str(keys_dir),
            "--out",
            str(tmp_path / "out"),
            "--bucket-name",
            "raw-output-contract",
            "--poll-interval",
            "0",
            "--max-polls",
            "1",
        ],
    )

    assert batch_extraction.main() == 0

    out_dir = tmp_path / "out"
    events = [json.loads(line) for line in (out_dir / "verify.log").read_text().splitlines()]
    assert not any(event["event"] == "verify.doc.done" for event in events)
    assert not (out_dir / "statement.extracted.json").exists()
    assert not (out_dir / "statement.final_output.json").exists()


def test_live_runners_do_not_import_local_business_logic():
    """Live extraction must not regain a local output-matching dependency."""
    for filename in ("run_extraction.py", "batch_extraction.py"):
        tree = ast.parse((TEMPLATES / filename).read_text(encoding="utf-8"))
        imported_modules = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert "business_logic" not in imported_modules, filename
