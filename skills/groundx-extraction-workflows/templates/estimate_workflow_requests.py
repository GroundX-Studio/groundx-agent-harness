#!/usr/bin/env python3
"""Estimate custom extraction request fanout before live ingest.

The estimate is intentionally offline. It reads a harness workflow YAML or a
compiled workflow JSON, counts PDF pages with pypdf when PDFs are supplied, and
projects how many custom extraction requests the workflow can create.
"""

import argparse
import json
import math
import os
import sys
import typing

import yaml


DEFAULT_CAP = 2000
DEFAULT_WARNING_THRESHOLD = 1500
DEFAULT_FALLBACK_CHUNKS_PER_PAGE = (1.0, 3.0, 5.0)
DEFAULT_PLAUSIBLE_LARGE_PAGES = 200


def count_pdf_pages(path: str) -> int:
    """Return the page count for one PDF, failing with an actionable message."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for PDF page counting. Install template "
            "dependencies with `pip install -r requirements.txt`."
        ) from exc

    try:
        reader = PdfReader(path)
        pages = len(reader.pages)
    except Exception as exc:
        raise RuntimeError(f"could not count PDF pages for {path}: {exc}") from exc

    if pages <= 0:
        raise RuntimeError(f"could not count PDF pages for {path}: no pages found")
    return pages


def load_workflow(path: str) -> dict:
    """Load a source YAML or compiled JSON workflow from disk."""
    with open(path, "r") as f:
        text = f.read()
    if path.endswith(".json"):
        payload = json.loads(text)
    else:
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: workflow must be a mapping/object")
    return payload


def _workflow_contract(workflow: dict) -> tuple[list[dict], typing.Optional[str]]:
    """Return custom steps and section strategy from source, compiled, or readback."""
    if isinstance(workflow.get("workflow"), dict):
        source_workflow = typing.cast(dict, workflow["workflow"])
        steps = source_workflow.get("custom_steps") or source_workflow.get("customSteps")
        section_strategy = (
            source_workflow.get("section_strategy")
            or source_workflow.get("sectionStrategy")
            or workflow.get("section_strategy")
            or workflow.get("sectionStrategy")
        )
        return list(steps or []), typing.cast(typing.Optional[str], section_strategy)

    steps = workflow.get("customSteps") or workflow.get("custom_steps")
    section_strategy = workflow.get("section_strategy") or workflow.get("sectionStrategy")
    if steps:
        return list(steps), typing.cast(typing.Optional[str], section_strategy)

    extract = workflow.get("extract")
    if isinstance(extract, dict):
        return _workflow_contract(extract)

    return [], typing.cast(typing.Optional[str], section_strategy)


def _step_counts(steps: list[dict]) -> dict[str, int]:
    counts = {"chunk": 0, "section": 0, "document": 0}
    for step in steps:
        level = step.get("level") if isinstance(step, dict) else None
        if level in counts:
            counts[typing.cast(str, level)] += 1
    return counts


def _page_scenarios(
    page_counts: list[int],
    expected_pages: typing.Optional[int],
    plausible_large_pages: int,
) -> tuple[list[dict], str]:
    if expected_pages:
        return [{"name": "expected_pages", "pages": int(expected_pages)}], "expected"

    if not page_counts:
        return [{"name": "plausible_large_document", "pages": plausible_large_pages}], "missing"

    confidence = "strong" if len(page_counts) >= 3 else "weak"
    scenarios: list[dict] = [
        {"name": "observed_max", "pages": max(page_counts)},
    ]
    if len(page_counts) >= 2:
        scenarios.insert(
            0,
            {"name": "observed_average", "pages": math.ceil(sum(page_counts) / len(page_counts))},
        )
    if confidence == "weak":
        scenarios.append(
            {
                "name": "plausible_large_document",
                "pages": max(max(page_counts), plausible_large_pages),
            }
        )
    return scenarios, confidence


def _chunk_density_scenarios(chunks_per_page: typing.Optional[float]) -> tuple[list[dict], str]:
    if chunks_per_page:
        return [{"name": "supplied_chunks_per_page", "chunks_per_page": float(chunks_per_page)}], "supplied"
    return [
        {"name": f"fallback_{density:g}_chunks_per_page", "chunks_per_page": density}
        for density in DEFAULT_FALLBACK_CHUNKS_PER_PAGE
    ], "fallback"


def estimate_request_fanout(
    workflow: dict,
    *,
    page_counts: typing.Optional[list[int]] = None,
    chunks_per_page: typing.Optional[float] = None,
    expected_pages: typing.Optional[int] = None,
    cap: int = DEFAULT_CAP,
    warning_threshold: int = DEFAULT_WARNING_THRESHOLD,
    plausible_large_pages: int = DEFAULT_PLAUSIBLE_LARGE_PAGES,
) -> dict:
    """Estimate custom extraction request fanout for a workflow/document set."""
    page_counts = [int(pages) for pages in (page_counts or []) if int(pages) > 0]
    steps, section_strategy = _workflow_contract(workflow)
    counts = _step_counts(steps)
    page_scenarios, sample_confidence = _page_scenarios(
        page_counts,
        expected_pages,
        plausible_large_pages,
    )
    density_scenarios, density_source = _chunk_density_scenarios(chunks_per_page)
    section_strategy_is_page = str(section_strategy or "").lower() == "page"
    unknown_section_fanout = counts["section"] > 0 and not section_strategy_is_page

    scenarios: list[dict] = []
    per_document_estimates: list[dict] = []
    for page_scenario in page_scenarios:
        pages = int(page_scenario["pages"])
        for density_scenario in density_scenarios:
            density = float(density_scenario["chunks_per_page"])
            chunk_requests = pages * density * counts["chunk"]
            section_requests: typing.Optional[float]
            if counts["section"] and not section_strategy_is_page:
                section_requests = None
            else:
                section_requests = pages * counts["section"]
            total = (
                math.ceil(chunk_requests)
                + (math.ceil(section_requests) if section_requests is not None else 0)
                + counts["document"]
            )
            scenarios.append(
                {
                    "name": page_scenario["name"],
                    "pages": pages,
                    "chunk_density_name": density_scenario["name"],
                    "chunks_per_page": density,
                    "chunk_requests": math.ceil(chunk_requests),
                    "section_requests": (
                        math.ceil(section_requests) if section_requests is not None else "unknown_high_risk"
                    ),
                    "document_requests": counts["document"],
                    "estimated_requests": total,
                }
            )

    for pages in page_counts:
        per_doc_max = 0
        for density_scenario in density_scenarios:
            density = float(density_scenario["chunks_per_page"])
            section_requests = pages * counts["section"] if section_strategy_is_page else 0
            total = math.ceil(pages * density * counts["chunk"]) + math.ceil(section_requests) + counts["document"]
            per_doc_max = max(per_doc_max, total)
        per_document_estimates.append({"pages": pages, "max_estimated_requests": per_doc_max})

    max_estimate = max((scenario["estimated_requests"] for scenario in scenarios), default=0)
    if max_estimate >= cap:
        risk_status = "block"
    elif unknown_section_fanout:
        risk_status = "unknown_high_risk"
    elif max_estimate >= warning_threshold:
        risk_status = "warning"
    else:
        risk_status = "ok"

    return {
        "risk_status": risk_status,
        "cap": cap,
        "warning_threshold": warning_threshold,
        "max_estimated_requests": max_estimate,
        "page_evidence": {
            "page_counts": page_counts,
            "average_pages": math.ceil(sum(page_counts) / len(page_counts)) if page_counts else None,
            "max_pages": max(page_counts) if page_counts else None,
        },
        "sample_confidence": sample_confidence,
        "chunk_density_source": density_source,
        "section_strategy": section_strategy,
        "unknown_section_fanout": unknown_section_fanout,
        "step_counts": counts,
        "scenarios": scenarios,
        "per_document_estimates": per_document_estimates,
        "recommended_action": _recommended_action(risk_status, unknown_section_fanout),
    }


def _recommended_action(risk_status: str, unknown_section_fanout: bool) -> str:
    if risk_status == "block":
        return (
            "Projected custom extraction requests reach the cap. Reduce chunk-level "
            "passes or move broad statement-style groups to section_strategy: page "
            "with level: section before live ingest."
        )
    if risk_status == "unknown_high_risk" or unknown_section_fanout:
        return (
            "Section-level fanout is unknown because workflow.section_strategy: page "
            "is absent. Add page section strategy or override explicitly."
        )
    if risk_status == "warning":
        return "Projected requests are near the cap; prefer a lower-fanout strategy before widening the batch."
    return "Projected requests are below the warning threshold for the supplied evidence."


def estimate_from_paths(
    workflow_path: str,
    *,
    pdf_paths: typing.Optional[list[str]] = None,
    chunks_per_page: typing.Optional[float] = None,
    expected_pages: typing.Optional[int] = None,
    cap: int = DEFAULT_CAP,
    warning_threshold: int = DEFAULT_WARNING_THRESHOLD,
) -> dict:
    workflow = load_workflow(workflow_path)
    page_counts = [count_pdf_pages(path) for path in (pdf_paths or [])]
    return estimate_request_fanout(
        workflow,
        page_counts=page_counts,
        chunks_per_page=chunks_per_page,
        expected_pages=expected_pages,
        cap=cap,
        warning_threshold=warning_threshold,
    )


def _format_text(report: dict) -> str:
    lines = [
        f"risk_status: {report['risk_status']}",
        f"max_estimated_requests: {report['max_estimated_requests']}",
        f"step_counts: {report['step_counts']}",
        f"sample_confidence: {report['sample_confidence']}",
        f"chunk_density_source: {report['chunk_density_source']}",
        f"recommended_action: {report['recommended_action']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-yaml", default=None, help="source workflow YAML")
    parser.add_argument("--workflow-json", default=None, help="compiled workflow JSON")
    parser.add_argument("--pdf", action="append", default=[], help="PDF to count; repeat for batches")
    parser.add_argument("--chunks-per-page", type=float, default=None)
    parser.add_argument("--expected-pages", type=int, default=None)
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--warning-threshold", type=int, default=DEFAULT_WARNING_THRESHOLD)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    workflow_path = args.workflow_yaml or args.workflow_json
    if not workflow_path:
        parser.error("one of --workflow-yaml or --workflow-json is required")

    try:
        report = estimate_from_paths(
            workflow_path,
            pdf_paths=args.pdf,
            chunks_per_page=args.chunks_per_page,
            expected_pages=args.expected_pages,
            cap=args.cap,
            warning_threshold=args.warning_threshold,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(_format_text(report))
    return 0 if report["risk_status"] not in {"block", "unknown_high_risk"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
