#!/usr/bin/env python3
"""Batch verification: run an extraction workflow over a folder of documents and
score every result against matching mapped expected-answer JSON files, producing
one consolidated field-level accuracy report.

This is the harness's verification loop made batch: a customer hands over a
folder of documents and expected answers, the agent maps those answers to
runner-shaped JSON files with the same base filename, authors a `prompt.yaml`,
and this command answers "how accurate is the extraction, field by field, across
the set — and where does it miss?".

    python batch_extraction.py \\
        --yaml prompt.yaml \\
        --docs-dir docs/ \\
        --keys-dir expected_answers/ \\
        --out run/ \\
        --bucket-name verify-customer-v1 \\
        --limit 5            # economical: score a representative subset first

Run artifacts (written to --out, a self-contained, reproducible set):
  - `prompt.yaml`            — the schema this run used (copied verbatim).
  - `workflow.json`          — the exact compiled workflow it deployed.
  - `<doc>.extracted.json`   — raw GroundX `get_extract` JSON when available.
  - `<doc>.xray.json`        — the raw X-Ray per document (cacheable input;
                               re-score with xray_to_extract → compare, NO re-ingest).
  - `<doc>.xray_diagnostic.json` — local X-Ray reconstruction when raw extract is missing.
  - `<doc>.final_output.json` — local diagnostic/business-logic output when produced.
  - `aggregated.accuracy.json`   — the consolidated field-level accuracy report.
  - `verify.log`             — structured run event log.

Design notes:
  - ONE workflow + bucket for the whole batch (compiled/deployed once).
  - Per document: ingest → poll → X-Ray → get_extract → optional local
    X-Ray diagnostic/final output → compare against expected-answer JSON.
  - Raw `<doc>.extracted.json` is scored by default. Use `--score-final-output`
    to score local final output for runs where `get_extract` is unavailable.
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

from compile_workflow import build_workflow_artifacts, workflow_sdk_kwargs  # noqa: E402
import score_extraction as cmp  # noqa: E402
from batch_score import aggregate_reports  # noqa: E402
from run_extraction import _load_business_logic_metadata, _poll, derive_extraction_artifacts  # noqa: E402
from run_log import RunLog  # noqa: E402
from validate_workflow_json import validate as validate_workflow  # noqa: E402


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
    workflow: dict[str, typing.Any],
    workflow_name: str,
) -> typing.Any:
    return gx.workflows.create(**workflow_sdk_kwargs(workflow))


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
    p.add_argument(
        "--score-final-output",
        action="store_true",
        help="Score <doc>.final_output.json when raw <doc>.extracted.json is unavailable",
    )
    p.add_argument("--poll-interval", type=int, default=15)
    p.add_argument("--max-polls", type=int, default=80)
    p.add_argument("--keep", action="store_true", help="keep workflow after run")
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
    bl_meta = _load_business_logic_metadata(args.yaml)
    workflow_name = args.workflow_name or os.path.splitext(os.path.basename(args.yaml))[0]

    with RunLog(os.path.join(args.out, "verify.log")) as rl:
        rl.event("verify.start", yaml=args.yaml, docs=len(docs), out=args.out)
        wf, extraction_metadata = build_workflow_artifacts(args.yaml, name=workflow_name)
        errors = validate_workflow(wf)
        if errors:
            rl.event("validate.error", errors=errors)
            raise SystemExit("workflow validation failed:\n  - " + "\n  - ".join(errors))
        # Snapshot the run inputs so the out dir is a self-contained, reproducible
        # artifact set (prompt schema + the exact compiled workflow it ran).
        with open(os.path.join(args.out, "prompt.yaml"), "w") as f:
            with open(args.yaml) as src:
                f.write(src.read())
        with open(os.path.join(args.out, "workflow.json"), "w") as f:
            json.dump(wf, f, indent=2, default=str)
        with open(os.path.join(args.out, "extraction_workflow_metadata_v1.json"), "w") as f:
            json.dump(extraction_metadata, f, indent=2, default=str)
        created = _create_workflow(gx, args.yaml, wf, workflow_name)
        workflow_id = _workflow_id(created)
        if args.add_to_account:
            gx.workflows.add_to_account(workflow_id=workflow_id)
        bucket_id = gx.buckets.create(name=args.bucket_name).bucket.bucket_id
        gx.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)
        rl.event("verify.deployed", workflow_id=workflow_id, bucket_id=bucket_id)
        workflow_extract = wf.get("extract")

        per_doc = []
        try:
            for doc_path in docs:
                base = os.path.splitext(os.path.basename(doc_path))[0]
                key_path = cmp.find_answer_key(keys_dir, base)
                if not key_path:
                    rl.event("verify.doc.skip", doc=base, reason="no expected-answer JSON")
                    continue
                ingest = gx.ingest(documents=[Document(bucket_id=bucket_id, file_path=doc_path,
                                                       file_name=os.path.basename(doc_path), file_type="pdf")])
                document_id = _poll(gx, ingest.ingest.process_id, args.poll_interval, args.max_polls, rl)
                artifacts = derive_extraction_artifacts(
                    gx,
                    document_id,
                    bl_meta,
                    rl,
                    workflow_extract=workflow_extract,
                )
                raw_extract = artifacts["raw_extract"]
                diagnostic_extract = artifacts["diagnostic_extract"]
                final_output = artifacts["final_output"]
                xray = artifacts["xray"]
                with open(os.path.join(args.out, f"{base}.xray.json"), "w") as f:
                    json.dump(xray, f, indent=2, default=str)
                if raw_extract is not None:
                    with open(os.path.join(args.out, f"{base}.extracted.json"), "w") as f:
                        json.dump(raw_extract, f, indent=2, default=str)
                if diagnostic_extract is not None:
                    with open(os.path.join(args.out, f"{base}.xray_diagnostic.json"), "w") as f:
                        json.dump(diagnostic_extract, f, indent=2, default=str)
                if final_output is not None:
                    with open(os.path.join(args.out, f"{base}.final_output.json"), "w") as f:
                        json.dump(final_output, f, indent=2, default=str)

                score_source = "raw"
                score_extract = raw_extract
                if score_extract is None and args.score_final_output:
                    score_source = "final"
                    score_extract = final_output
                if score_extract is None:
                    rl.event(
                        "verify.doc.partial",
                        doc=base,
                        reason="raw get_extract unavailable; use --score-final-output to score local output",
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
