#!/usr/bin/env python3
"""Structural self-check on a compiled GroundX workflow JSON.

Catches custom-workflow wiring regressions before live ingest: missing custom
steps, incomplete output routes, missing leaf fields, unrouted extract fields,
and the older slot serialization class where required null keys disappeared
from the generated `steps` object.

Run after `compile_workflow.py` and before any live ingest. Failing here
costs nothing; failing after a 5–15 minute ingest costs quota and time.

Usage:
    python validate_workflow_json.py workflow.json

Exits 0 if the JSON has the full expected shape. Exits 1 with explicit
error messages otherwise.

Validated:
    - top-level: `extract` and `steps` dicts present
    - `steps`: all GroundX workflow step keys present (may be null)
    - each non-null step: all 6 `WorkflowStep` variant keys present
      (may be null): all, figure, paragraph, json, table, table-figure
    - custom workflows include matching `customSteps`, `outputRoutes`, and
      `leafFields`
    - every final extract field has a custom output route when custom workflow
      fields are present
"""

import argparse
import json
import re
import sys
import typing


# Matches Python format placeholders like {field_desc} that should have
# been substituted by a `.format()` call. The lookbehind/lookahead excludes
# `{{` and `}}` escapes. Identifier pattern matches typical kwarg names.
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{[a-zA-Z_][a-zA-Z0-9_]*\}(?!\})")


REQUIRED_SLOTS = [
    "chunk-instruct",
    "chunk-keys",
    "chunk-summary",
    "doc-keys",
    "doc-summary",
    "search-query",
    "sect-instruct",
    "sect-keys",
    "sect-summary",
]

REQUIRED_VARIANTS = ["all", "figure", "paragraph", "json", "table", "table-figure"]
CUSTOM_STEP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CUSTOM_WORKFLOW_MAX_FIELDS = 20
CUSTOM_OUTPUT_MAPS = {
    "chunk": "customChunkOutputs",
    "section": "customSectionOutputs",
    "document": "customDocumentOutputs",
}
REPEATED_CUSTOM_STEP_KINDS = {"keys", "summary"}
RESERVED_CUSTOM_NAMES = {
    "workflow",
    "template",
    "custom_steps",
    "customSteps",
    "output_routes",
    "outputRoutes",
    "leaf_fields",
    "leafFields",
    "chunk_keys",
    "chunk_summary",
    "chunk_instruct",
    "doc_keys",
    "doc_summary",
    "sect_keys",
    "sect_summary",
    "sect_instruct",
}
RESERVED_EXTRACT_KEYS = {
    "workflow",
    "_defs",
    "_pseudo_groups",
    "_groundx_persisted_extract",
}


def _scan_placeholders(obj: typing.Any, path: str = "") -> typing.Iterator[typing.Tuple[str, str]]:
    """Yield (path, placeholder) for every unresolved `{name}` in any string."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _scan_placeholders(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _scan_placeholders(item, f"{path}[{i}]")
    elif isinstance(obj, str):
        for match in _PLACEHOLDER_RE.finditer(obj):
            yield path, match.group(0)


def _pointer_segments(pointer: typing.Any, path: str, errors: typing.List[str]) -> typing.Tuple[str, ...]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        errors.append(f"{path} must be an RFC 6901 JSON pointer")
        return ()
    parts = tuple(part for part in pointer.split("/")[1:] if part)
    if not parts:
        errors.append(f"{path} must point to a field")
    return parts


def _readback_path(level: str, step_name: str, output_key: str) -> str:
    output_map = CUSTOM_OUTPUT_MAPS[level]
    if level == "document":
        return f"/{output_map}/{step_name}/{output_key}"
    return f"/chunks/*/{output_map}/{step_name}/{output_key}"


def _custom_match_key(item: dict) -> tuple:
    return (
        item.get("finalPath"),
        item.get("workflowGroup"),
        item.get("workflowField"),
        item.get("stepName"),
        item.get("level"),
        item.get("outputKey"),
    )


def _final_field_pointer(group_name: str, field_name: str) -> str:
    return f"/{group_name}/{field_name}"


def _normalize_final_pointer(pointer: typing.Any) -> typing.Optional[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    parts = [part for part in pointer.split("/")[1:] if part and part != "*"]
    if len(parts) < 2:
        return None
    return "/" + "/".join(parts)


def _extract_final_field_pointers(extract: typing.Any) -> typing.Iterator[tuple[str, str, str]]:
    if not isinstance(extract, dict):
        return
    for group_name, group_data in extract.items():
        if group_name in RESERVED_EXTRACT_KEYS or str(group_name).startswith("_"):
            continue
        if not isinstance(group_data, dict):
            continue
        fields = group_data.get("fields")
        if not isinstance(fields, dict):
            continue
        for field_name in fields:
            yield str(group_name), str(field_name), _final_field_pointer(str(group_name), str(field_name))


def _validate_custom_workflow(workflow: dict) -> typing.List[str]:
    errors: typing.List[str] = []
    custom_steps = workflow.get("customSteps") or []
    output_routes = workflow.get("outputRoutes") or []
    leaf_fields = workflow.get("leafFields") or []

    if not isinstance(custom_steps, list):
        return ["customSteps must be an array"]
    if not isinstance(output_routes, list):
        return ["outputRoutes must be an array"]
    if not isinstance(leaf_fields, list):
        return ["leafFields must be an array"]
    if not custom_steps and not output_routes and not leaf_fields:
        return []
    if not custom_steps or not output_routes or not leaf_fields:
        errors.append("custom workflow requires customSteps, outputRoutes, and leafFields")
        return errors

    steps_by_name: typing.Dict[str, dict] = {}
    for index, step in enumerate(custom_steps):
        if not isinstance(step, dict):
            errors.append(f"customSteps[{index}] must be an object")
            continue
        name = step.get("name")
        level = step.get("level")
        kind = step.get("kind")
        if not isinstance(name, str) or not CUSTOM_STEP_NAME_RE.match(name):
            errors.append(f"invalid custom step name at customSteps[{index}]: {name!r}")
            continue
        if name in RESERVED_CUSTOM_NAMES:
            errors.append(f"reserved custom step name at customSteps[{index}]: {name!r}")
            continue
        if name in steps_by_name:
            errors.append(f"duplicate custom step name: {name}")
            continue
        if level not in CUSTOM_OUTPUT_MAPS:
            errors.append(f"invalid custom step level for {name}: {level!r}")
            continue
        if kind not in {"instruct", "keys", "summary"}:
            errors.append(f"invalid custom step kind for {name}: {kind!r}")
            continue
        if level == "document" and kind == "instruct":
            errors.append(f"invalid custom step level/kind for {name}: {level}/{kind}")
            continue
        steps_by_name[name] = step

    routes_by_key: typing.Dict[tuple, dict] = {}
    route_destinations: typing.Set[tuple[str, str]] = set()
    field_counts: typing.Dict[str, int] = {}
    for index, route in enumerate(output_routes):
        if not isinstance(route, dict):
            errors.append(f"outputRoutes[{index}] must be an object")
            continue
        key = _custom_match_key(route)
        if key in routes_by_key:
            errors.append(f"duplicate route identity for {route.get('finalPath')}")
            continue
        routes_by_key[key] = route
        step_name = route.get("stepName")
        output_key = route.get("outputKey")
        step = steps_by_name.get(step_name)
        if step is None:
            errors.append(f"output route references unknown custom step {step_name!r}")
            continue
        if route.get("level") != step.get("level"):
            errors.append(f"output route level does not match custom step {step_name}")
        expected_map = CUSTOM_OUTPUT_MAPS[typing.cast(str, step.get("level"))]
        if route.get("outputMap") != expected_map:
            errors.append(f"output route outputMap must be {expected_map} for {step_name}")
        if not isinstance(output_key, str) or not CUSTOM_STEP_NAME_RE.match(output_key):
            errors.append(f"invalid output key for route {route.get('finalPath')}: {output_key!r}")
            continue
        destination = (typing.cast(str, step_name), output_key)
        if destination in route_destinations:
            errors.append(f"duplicate output destination {step_name}.{output_key}")
        route_destinations.add(destination)
        expected_readback = _readback_path(
            typing.cast(str, step.get("level")), typing.cast(str, step_name), output_key
        )
        if route.get("readbackPath") != expected_readback:
            errors.append(f"readbackPath for {step_name}.{output_key} must be {expected_readback}")
        segments = _pointer_segments(route.get("finalPath"), f"outputRoutes[{index}].finalPath", errors)
        if step.get("kind") in REPEATED_CUSTOM_STEP_KINDS and "*" not in segments:
            errors.append(
                f"output route {route.get('finalPath')} for repeated custom step "
                f"{step_name} must include a wildcard segment"
            )
        field_counts[typing.cast(str, step_name)] = field_counts.get(typing.cast(str, step_name), 0) + 1

    leaves_by_key: typing.Dict[tuple, dict] = {}
    for index, leaf in enumerate(leaf_fields):
        if not isinstance(leaf, dict):
            errors.append(f"leafFields[{index}] must be an object")
            continue
        key = _custom_match_key(leaf)
        if key in leaves_by_key:
            errors.append(f"duplicate leaf identity for {leaf.get('finalPath')}")
            continue
        leaves_by_key[key] = leaf
        step_name = leaf.get("stepName")
        step = steps_by_name.get(step_name)
        if step is None:
            errors.append(f"leaf field references unknown custom step {step_name!r}")
            continue
        if leaf.get("level") != step.get("level"):
            errors.append(f"leaf field level does not match custom step {step_name}")
        segments = _pointer_segments(leaf.get("finalPath"), f"leafFields[{index}].finalPath", errors)
        is_repeated = leaf.get("isRepeated")
        repetition_scope = leaf.get("repetitionScope")
        step_repeats = step.get("kind") in REPEATED_CUSTOM_STEP_KINDS
        if step_repeats:
            if is_repeated is not True:
                errors.append(
                    f"leaf field {leaf.get('finalPath')} for repeated custom step "
                    f"{step_name} must set isRepeated true"
                )
            if "*" not in segments:
                errors.append(
                    f"leaf field {leaf.get('finalPath')} for repeated custom step "
                    f"{step_name} must include a wildcard segment"
                )
            elif repetition_scope != "/" + "/".join(segments[: segments.index("*") + 1]):
                errors.append(
                    f"leaf field {leaf.get('finalPath')} for repeated custom step "
                    f"{step_name} has invalid repetitionScope"
                )
        if is_repeated is True:
            if "*" not in segments:
                errors.append(f"leaf field {leaf.get('finalPath')} is repeated but has no wildcard segment")
            elif repetition_scope != "/" + "/".join(segments[: segments.index("*") + 1]):
                errors.append(f"leaf field {leaf.get('finalPath')} has invalid repeated-item wildcard scope")
        elif is_repeated is False:
            if repetition_scope != "none":
                errors.append(f"leaf field {leaf.get('finalPath')} is not repeated but sets repetitionScope")
        else:
            errors.append(f"leafFields[{index}].isRepeated must be true or false")

    for key, route in routes_by_key.items():
        if key not in leaves_by_key:
            errors.append(f"missing leaf field for output route {route.get('finalPath')}")
    for key, leaf in leaves_by_key.items():
        if key not in routes_by_key:
            errors.append(f"missing output route for leaf field {leaf.get('finalPath')}")

    for step_name in steps_by_name:
        if step_name not in field_counts:
            errors.append(f"custom step '{step_name}' has no output routes")

    routed_final_fields = {
        normalized
        for route in output_routes
        for normalized in (_normalize_final_pointer(route.get("finalPath")),)
        if normalized
    }
    for group_name, field_name, pointer in _extract_final_field_pointers(workflow.get("extract")):
        if pointer not in routed_final_fields:
            errors.append(
                f"extract group '{group_name}' field '{field_name}' has no custom output route"
            )

    for step_name, count in field_counts.items():
        if count > CUSTOM_WORKFLOW_MAX_FIELDS:
            errors.append(
                f"custom step {step_name} owns {count} fields; at most 20 fields "
                "may route to one executable workflow step"
            )

    return errors


def validate(workflow: dict) -> typing.List[str]:
    errors: typing.List[str] = []

    for key in ("extract", "steps"):
        if key not in workflow:
            errors.append(f"missing top-level key: '{key}'")

    if "steps" not in workflow:
        return errors

    steps = workflow["steps"]
    if not isinstance(steps, dict):
        errors.append("'steps' must be an object")
        return errors

    for slot in REQUIRED_SLOTS:
        if slot not in steps:
            errors.append(
                f"steps missing slot key: '{slot}' "
                "(must be present, even if null — platform aggregator "
                "skips silently when slot keys are absent)"
            )

    errors.extend(_validate_custom_workflow(workflow))
    has_custom_steps = bool(workflow.get("customSteps"))

    ci = steps.get("chunk-instruct")
    ck = steps.get("chunk-keys")
    if ci is None and ck is None and not has_custom_steps:
        errors.append(
            "both 'chunk-instruct' and 'chunk-keys' are null — no extraction will run"
        )

    for slot in REQUIRED_SLOTS:
        step = steps.get(slot)
        if step is None:
            continue
        if not isinstance(step, dict):
            errors.append(f"steps['{slot}'] must be an object or null")
            continue
        for variant in REQUIRED_VARIANTS:
            if variant not in step:
                errors.append(
                    f"steps['{slot}'] missing variant: '{variant}' "
                    "(must be present, even if null)"
                )

    # Unresolved-placeholder scan: catches the silent-degradation class
    # where a `.format()` call drops a kwarg and emits literal `{name}`
    # text to the LLM. Scans both `steps` (where compile_workflow.py
    # builds prompt strings) and `extract` (defensive — customer YAMLs
    # land verbatim, but a future authoring tool may template them).
    for region in ("steps", "extract"):
        for path, placeholder in _scan_placeholders(workflow.get(region, {}), region):
            errors.append(
                f"unresolved placeholder {placeholder!r} in {path} "
                "— a `.format()` call did not substitute this value"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_path", help="Path to compiled workflow JSON")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success message; only print on failure",
    )
    args = parser.parse_args()

    with open(args.workflow_path) as f:
        wf = json.load(f)

    errors = validate(wf)
    if not errors:
        if not args.quiet:
            print(f"OK {args.workflow_path}: structural validation passed")
        return 0

    print(f"FAIL {args.workflow_path}: {len(errors)} structural error(s):", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
