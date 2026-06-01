#!/usr/bin/env python3
"""Synthesize a `get_extract()`-shaped dict locally from a captured X-Ray.

Reads `gx.documents.get_xray(document_id)` output (a JSON file containing
a `chunks` array) and reproduces the same shape `gx.documents.get_extract()`
returns. The point: once you have an X-Ray captured from one ingest, you
can iterate on comparison logic, field aliases, and dedupe rules locally
without paying for re-ingest. Only re-ingest when YAML or prompts actually
change.

Usage:
    python xray_to_extract.py xray.json > extract-from-xray.json

Or import as a module:
    from xray_to_extract import xray_to_extract
    extract_dict = xray_to_extract(xray_dict)

Charges aggregation: each chunk's `chunkKeywords` is parsed as JSON; the
top-level `charges` array (if present) is accumulated. Duplicate records
across chunks are removed by full-record hash (canonical JSON form).

Meters aggregation: each chunk's `chunkSummary` is parsed as JSON; the
top-level `meters` array (if present) is accumulated. Duplicate records
across chunks are removed by full-record hash.

Statement aggregation: each chunk's `sectionSummary` is parsed as JSON;
top-level scalar keys are merged into a single statement dict. First
non-empty value per key wins (matches the platform's apparent behavior
of taking the earliest confident extraction).
"""

import argparse
import json
import sys
import typing


def _parse_json_field(raw: typing.Any) -> typing.Optional[dict]:
    """Parse a chunk-level JSON-string field. Returns None on empty/invalid."""
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _record_key(record: dict) -> str:
    """Canonical hash key for a single charge record. Used for dedupe."""
    return json.dumps(record, sort_keys=True, default=str)


def xray_to_extract(xray: dict) -> dict:
    """Convert an X-Ray dict to a `get_extract()`-shaped dict."""
    chunks = xray.get("chunks") or []
    statement: dict = {}
    charges: list = []
    meters: list = []
    seen_charges: set = set()
    seen_meters: set = set()

    for chunk in chunks:
        # Charges from chunkKeywords
        kw = _parse_json_field(chunk.get("chunkKeywords"))
        if kw and isinstance(kw.get("charges"), list):
            for record in kw["charges"]:
                if not isinstance(record, dict):
                    continue
                key = _record_key(record)
                if key in seen_charges:
                    continue
                seen_charges.add(key)
                charges.append(record)

        # Meters from the chunk-sum output. Depending on the X-Ray shape it
        # surfaces under `chunkSummary` OR `suggestedText` (overriding `chunk-sum`
        # replaces the chunk's suggestedText — see 3_prompt_pipeline.md §7). Try
        # both; dedup by record key prevents double-counting.
        for src_field in ("chunkSummary", "suggestedText"):
            chunk_summary = _parse_json_field(chunk.get(src_field))
            if chunk_summary and isinstance(chunk_summary.get("meters"), list):
                for record in chunk_summary["meters"]:
                    if not isinstance(record, dict):
                        continue
                    key = _record_key(record)
                    if key in seen_meters:
                        continue
                    seen_meters.add(key)
                    meters.append(record)

        # Statement from sectionSummary
        ss = _parse_json_field(chunk.get("sectionSummary"))
        if ss:
            for field, value in ss.items():
                # Skip nested aggregations like nested account_charges in older pipelines
                if isinstance(value, (dict, list)):
                    continue
                if value in (None, "", []):
                    continue
                if field in statement and statement[field] not in (None, "", []):
                    continue
                statement[field] = value

    result = dict(statement)
    result["account_charges"] = charges
    result["meters"] = meters
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xray_path", help="Path to X-Ray JSON file")
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for stdout (default: 2)",
    )
    args = parser.parse_args()

    with open(args.xray_path) as f:
        xray = json.load(f)

    extract = xray_to_extract(xray)
    sys.stdout.write(json.dumps(extract, indent=args.indent, default=str))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
