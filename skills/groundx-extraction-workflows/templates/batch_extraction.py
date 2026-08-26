#!/usr/bin/env python3
"""Batch verification: run an extraction workflow over a folder of documents and
score every result against matching mapped expected-answer JSON files, producing
one consolidated field-level accuracy report.

This is the harness's verification loop made batch: a customer hands over a
folder of documents and expected answers, the agent maps those answers to
runner-shaped JSON files with the same base filename, authors a `prompt.yaml`,
and this command answers "how accurate is the extraction, field by field, across
the set — and where does it miss?".

Local output lifecycle: follow `references/local-artifact-closeout.md`; planned
callers pass the initialized absolute run root to `--out` before this script writes.

    python batch_extraction.py \\
        --yaml prompt.yaml \\
        --docs-dir docs/ \\
        --keys-dir expected_answers/ \\
        --out "$RUN_ROOT/batch" \\
        --bucket-name verify-customer-v1 \\
        --limit 5            # economical: score a representative subset first

Run artifacts (written to --out, a self-contained, reproducible set):
  - `prompt.yaml`            — the schema this run used (copied verbatim).
  - `workflow.json`          — server workflow readback saved for diagnostics.
  - `<doc>.extracted.json`   — raw GroundX `get_extract` JSON when available.
  - `<doc>.xray.json`        — the raw X-Ray per document (cacheable input;
                               re-score captured server output, NO re-ingest).
  - `aggregated.accuracy.json`   — the consolidated field-level accuracy report.
  - `verify.log`             — structured run event log.

Design notes:
  - ONE workflow + bucket for the whole batch (compiled/deployed once).
  - Per document: ingest → poll → X-Ray → get_extract → compare against
    expected-answer JSON.
  - Raw `<doc>.extracted.json` is the only live scoring input.
  - `aggregate_reports()` is a pure function (unit-tested) so the scoring/rollup
    is verifiable without any API calls.
  - `--limit` and an explicit doc list keep live cost economical; iterate on a
    subset, then widen once the YAML converges.
  - `--manifest` (csv with a `filename` column + any dimension columns such as
    `vendor`/`service_type`) adds per-dimension accuracy breakdowns.

Reads `.env` for `GROUNDX_API_KEY`. Real customer data must live outside the
repo (or in a gitignored path) — never commit documents or expected answers.
"""

import argparse
import glob
import json
import os
import sys
import typing

import dotenv

dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from groundx import Document, GroundX  # noqa: E402

from _workflow_source import load_workflow_source  # noqa: E402
import score_extraction as cmp  # noqa: E402
from batch_score import aggregate_reports  # noqa: E402
from run_extraction import (  # noqa: E402
    _poll,
    _request_estimate_preflight,
    _to_plain_dict,
    derive_extraction_artifacts,
)
from run_log import RunLog  # noqa: E402


# ── live batch orchestration ────────────────────────────────────────────────


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


def _create_workflow(
    gx: GroundX,
    yaml_path: str,
    workflow_name: str,
) -> typing.Any:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return gx.workflows.create(name=workflow_name, yaml=f.read())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yaml", required=True)
    p.add_argument("--docs-dir", required=True)
    p.add_argument("--keys-dir", default=None, help="mapped expected-answer JSON dir (default: --docs-dir)")
    p.add_argument("--out", required=True)
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--workflow-name", default=None)
    p.add_argument("--limit", type=int, default=0, help="max docs to process (0 = all)")
    p.add_argument("--manifest", default=None, help="csv with filename + dimension columns")
    p.add_argument("--add-to-account", action="store_true")
    p.add_argument("--poll-interval", type=int, default=15)
    p.add_argument("--max-polls", type=int, default=80)
    p.add_argument("--keep", action="store_true", help="keep workflow after run")
    p.add_argument(
        "--allow-high-request-estimate",
        action="store_true",
        help="Proceed even when request-fanout preflight reaches the risk threshold",
    )
    args = p.parse_args()

    keys_dir = args.keys_dir or args.docs_dir
    os.makedirs(args.out, exist_ok=True)
    api_key = os.environ.get("GROUNDX_API_KEY")
    if not api_key:
        print("ERROR: GROUNDX_API_KEY is not set", file=sys.stderr)
        return 2
    gx = GroundX(api_key=api_key, base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"))

    docs = sorted(glob.glob(os.path.join(args.docs_dir, "*.pdf")))
    if args.limit:
        docs = docs[: args.limit]
    if not docs:
        print(f"no .pdf documents under {args.docs_dir}", file=sys.stderr)
        return 2
    manifest = cmp.load_manifest(args.manifest)
    selected_docs: list[str] = []
    skipped_docs: list[str] = []
    answer_keys: dict[str, str] = {}
    for doc_path in docs:
        base = os.path.splitext(os.path.basename(doc_path))[0]
        key_path = cmp.find_answer_key(keys_dir, base)
        if not key_path:
            skipped_docs.append(base)
            continue
        selected_docs.append(doc_path)
        answer_keys[base] = key_path
    if not selected_docs:
        print("no documents with matching expected-answer JSON after selection", file=sys.stderr)
        return 2
    workflow_name = args.workflow_name or os.path.splitext(os.path.basename(args.yaml))[0]

    with RunLog(os.path.join(args.out, "verify.log")) as rl:
        rl.event(
            "verify.start",
            yaml=args.yaml,
            docs=len(selected_docs),
            discovered_docs=len(docs),
            out=args.out,
        )
        for base in skipped_docs:
            rl.event("verify.doc.skip", doc=base, reason="no expected-answer JSON")
        source = load_workflow_source(args.yaml)
        with open(args.yaml, "r", encoding="utf-8") as src:
            yaml_text = src.read()
        try:
            gx.workflows.validate(name=workflow_name, yaml=yaml_text)
        except Exception as exc:
            rl.event("validate.error", error=str(exc))
            raise SystemExit(f"workflow validation failed: {exc}")
        # Snapshot the authored input exactly. Cashbot owns derived workflow metadata.
        with open(os.path.join(args.out, "prompt.yaml"), "w") as f:
            f.write(yaml_text)
        if not _request_estimate_preflight(
            rl,
            args.out,
            source,
            selected_docs,
            allow_high_request_estimate=args.allow_high_request_estimate,
        ):
            return 2
        created = _create_workflow(gx, args.yaml, workflow_name)
        workflow_id = _workflow_id(created)
        with open(os.path.join(args.out, "workflow.json"), "w") as f:
            json.dump(_to_plain_dict(created), f, indent=2, default=str)
        if args.add_to_account:
            gx.workflows.add_to_account(workflow_id=workflow_id)
        bucket_id = gx.buckets.create(name=args.bucket_name).bucket.bucket_id
        gx.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)
        rl.event("verify.deployed", workflow_id=workflow_id, bucket_id=bucket_id)
        per_doc = []
        try:
            for doc_path in selected_docs:
                base = os.path.splitext(os.path.basename(doc_path))[0]
                key_path = answer_keys[base]
                ingest = gx.ingest(documents=[Document(bucket_id=bucket_id, file_path=doc_path,
                                                       file_name=os.path.basename(doc_path), file_type="pdf")])
                document_id = _poll(gx, ingest.ingest.process_id, args.poll_interval, args.max_polls, rl)
                artifacts = derive_extraction_artifacts(
                    gx,
                    document_id,
                    rl=rl,
                )
                raw_extract = artifacts["raw_extract"]
                xray = artifacts["xray"]
                with open(os.path.join(args.out, f"{base}.xray.json"), "w") as f:
                    json.dump(xray, f, indent=2, default=str)
                if raw_extract is not None:
                    with open(os.path.join(args.out, f"{base}.extracted.json"), "w") as f:
                        json.dump(raw_extract, f, indent=2, default=str)
                score_source = "raw"
                score_extract = raw_extract
                if score_extract is None:
                    rl.event(
                        "verify.doc.partial",
                        doc=base,
                        reason="raw get_extract unavailable; no scoreable server output",
                    )
                    continue

                expected = cmp.load_answer_key(key_path)
                report = cmp.compare_extraction(score_extract, expected)
                per_doc.append({"doc": base, "report": report, "score_source": score_source})
                rl.event(
                    "verify.doc.done",
                    doc=base,
                    score_source=score_source,
                    accuracy=report["summary"]["singleton"],
                )
        finally:
            if not args.keep:
                try:
                    gx.workflows.delete(id=workflow_id)
                    rl.event("verify.cleanup", workflow_id=workflow_id)
                    rl.event(
                        "cleanup.bucket.preserved",
                        bucket_id=bucket_id,
                        reason="bucket deletion is not a supported harness cleanup path",
                    )
                except Exception as e:
                    rl.event("verify.cleanup.error", error=str(e)[:120])

        summary = aggregate_reports(per_doc, manifest)
        with open(os.path.join(args.out, "aggregated.accuracy.json"), "w") as f:
            json.dump(summary, f, indent=2, default=str)
        rl.event("verify.done", documents=summary["documents"], overall=summary["overall_accuracy"])

    print(f"verify complete: {summary['documents']} docs, overall {summary['overall_accuracy']:.1%}")
    print(f"  structural failures: {summary['docs_with_structural_failure']}")
    print(f"  report: {os.path.join(args.out, 'aggregated.accuracy.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
