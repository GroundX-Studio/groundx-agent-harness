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

Custom workflow aggregation: when a compiled workflow extract is provided,
`workflow.output_routes` reads `customChunkOutputs`, `customSectionOutputs`, or
`customDocumentOutputs` and writes values back to their final JSON Pointer
paths.

Legacy fallback aggregation: each chunk's `chunkKeywords` is parsed as JSON; the
top-level `charges` array (if present) is accumulated. Duplicate records across
chunks are removed by full-record hash (canonical JSON form).

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

_REPEATED_STEP_KINDS = {"keys", "summary"}


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


def _chunk_identity(chunk: dict) -> str:
    for key in ("chunkId", "chunk_id", "id"):
        value = chunk.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    return _record_key(chunk)


def _iter_chunks(xray: dict) -> typing.Iterator[dict]:
    top_level_keys: set[str] = set()
    for chunk in xray.get("chunks") or []:
        if isinstance(chunk, dict):
            top_level_keys.add(_chunk_identity(chunk))
            yield chunk
    for page in xray.get("documentPages") or []:
        if not isinstance(page, dict):
            continue
        for chunk in page.get("chunks") or []:
            if isinstance(chunk, dict):
                if _chunk_identity(chunk) in top_level_keys:
                    continue
                yield chunk


def _custom_route_values(
    container: dict,
    route: dict,
    *,
    repeated: bool,
) -> list[tuple[typing.Optional[int], typing.Any]]:
    output_map = container.get(route.get("output_map"))
    if not isinstance(output_map, dict):
        return []
    step_value = output_map.get(route.get("step_name"))
    output_key = route.get("output_key")

    if repeated and isinstance(step_value, list):
        values: list[tuple[typing.Optional[int], typing.Any]] = []
        for index, row in enumerate(step_value):
            if isinstance(row, dict):
                values.append((index, row.get(output_key)))
            else:
                values.append((index, row))
        return values

    if isinstance(step_value, dict):
        value = step_value.get(output_key)
        if repeated and isinstance(value, list):
            return [(index, item) for index, item in enumerate(value)]
        return [(None, value)]

    return [(None, step_value)]


def _set_nested_value(record: dict, parts: list[str], value: typing.Any) -> None:
    current = record
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            return
        current = next_value
    current[parts[-1]] = value


def _custom_step_kinds(workflow: dict) -> dict[str, str]:
    step_kinds: dict[str, str] = {}
    for step in workflow.get("custom_steps") or []:
        if not isinstance(step, dict):
            continue
        name = step.get("name")
        kind = step.get("kind")
        if isinstance(name, str) and isinstance(kind, str):
            step_kinds[name] = kind
    return step_kinds


def _repeat_pointer_for_step(pointer: str, *, should_repeat: bool) -> str:
    if not should_repeat or "*" in pointer:
        return pointer
    parts = [part for part in pointer.split("/")[1:] if part]
    if len(parts) < 2:
        return pointer
    return "/" + "/".join([*parts[:-1], "*", parts[-1]])


def _set_pointer(
    result: dict,
    pointer: str,
    value: typing.Any,
    *,
    repeated_records: dict[tuple[tuple[str, ...], tuple[typing.Any, ...]], dict],
    record_key: tuple[typing.Any, ...],
) -> None:
    parts = [part for part in pointer.split("/")[1:] if part]
    if not parts:
        return
    if "*" in parts:
        star_index = parts.index("*")
        list_path = parts[:star_index]
        if not list_path:
            return
        current = result
        for part in list_path[:-1]:
            next_value = current.setdefault(part, {})
            if not isinstance(next_value, dict):
                return
            current = next_value
        list_name = list_path[-1]
        records = current.setdefault(list_name, [])
        if not isinstance(records, list):
            return
        item_key = (tuple(list_path), record_key)
        record = repeated_records.get(item_key)
        if record is None:
            record = {}
            repeated_records[item_key] = record
            records.append(record)
        field_path = parts[star_index + 1 :]
        if field_path:
            _set_nested_value(record, field_path, value)
        return

    current = result
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            return
        current = next_value
    current[parts[-1]] = value


def _apply_custom_outputs(result: dict, xray: dict, workflow_extract: typing.Optional[dict]) -> None:
    if not workflow_extract:
        return
    workflow = workflow_extract.get("workflow")
    if not isinstance(workflow, dict):
        return
    routes = workflow.get("output_routes") or []
    if not isinstance(routes, list):
        return
    step_kinds = _custom_step_kinds(workflow)

    containers_by_level = {
        "document": [xray],
        "chunk": list(_iter_chunks(xray)),
        "section": list(_iter_chunks(xray)),
    }
    seen_repeated: set[tuple[str, tuple[typing.Any, ...], str]] = set()
    repeated_records: dict[tuple[tuple[str, ...], tuple[typing.Any, ...]], dict] = {}
    for route in routes:
        if not isinstance(route, dict):
            continue
        containers = containers_by_level.get(route.get("level"), [])
        for container_index, container in enumerate(containers):
            final_path = route.get("final_path")
            if not isinstance(final_path, str):
                continue
            step_name = route.get("step_name")
            is_repeated_step = step_kinds.get(step_name) in _REPEATED_STEP_KINDS
            final_path = _repeat_pointer_for_step(
                final_path,
                should_repeat=is_repeated_step,
            )
            for record_index, value in _custom_route_values(
                container,
                route,
                repeated=is_repeated_step,
            ):
                if value in (None, "", []):
                    continue
                record_key = (route.get("level"), container_index, step_name, record_index)
                key = (
                    final_path,
                    record_key,
                    _record_key(value) if isinstance(value, dict) else str(value),
                )
                if "*" in final_path and key in seen_repeated:
                    continue
                seen_repeated.add(key)
                _set_pointer(
                    result,
                    final_path,
                    value,
                    repeated_records=repeated_records,
                    record_key=record_key,
                )


def _has_custom_output_routes(workflow_extract: typing.Optional[dict]) -> bool:
    if not workflow_extract:
        return False
    workflow = workflow_extract.get("workflow")
    if not isinstance(workflow, dict):
        return False
    routes = workflow.get("output_routes")
    return isinstance(routes, list) and len(routes) > 0


def _merge_fallback_records(result: dict, key: str, records: list) -> None:
    existing = result.get(key)
    if not isinstance(existing, list):
        if key not in result:
            result[key] = records
        return

    seen = {_record_key(record) for record in existing if isinstance(record, dict)}
    for record in records:
        if not isinstance(record, dict):
            existing.append(record)
            continue
        record_key = _record_key(record)
        if record_key in seen:
            continue
        seen.add(record_key)
        existing.append(record)


def xray_to_extract(xray: dict, workflow_extract: typing.Optional[dict] = None) -> dict:
    """Convert an X-Ray dict to a `get_extract()`-shaped dict."""
    has_custom_routes = _has_custom_output_routes(workflow_extract)
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

        # Legacy meters fallback. Custom workflows should route meter values
        # through workflow.output_routes and custom*Outputs above; older captures
        # may still surface meter JSON in chunkSummary or suggestedText.
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

    result = {} if has_custom_routes else dict(statement)
    _apply_custom_outputs(result, xray, workflow_extract)
    if has_custom_routes:
        return result
    _merge_fallback_records(result, "account_charges", charges)
    _merge_fallback_records(result, "meters", meters)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xray_path", help="Path to X-Ray JSON file")
    parser.add_argument(
        "--workflow-json",
        default=None,
        help="Optional compiled workflow.json whose extract.workflow routes custom outputs",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for stdout (default: 2)",
    )
    args = parser.parse_args()

    with open(args.xray_path) as f:
        xray = json.load(f)
    workflow_extract = None
    if args.workflow_json:
        with open(args.workflow_json) as f:
            workflow_extract = (json.load(f) or {}).get("extract")

    extract = xray_to_extract(xray, workflow_extract=workflow_extract)
    sys.stdout.write(json.dumps(extract, indent=args.indent, default=str))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
