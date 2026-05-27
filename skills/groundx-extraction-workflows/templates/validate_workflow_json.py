#!/usr/bin/env python3
"""Structural self-check on a compiled GroundX workflow JSON.

Catches the slot-wiring regression class: Pydantic serialization silently
dropping unset fields, producing a workflow the platform accepts but
doesn't recognize as fully configured. The `chunk_keys → account_charges`
aggregator skips when slot keys are missing, and `get_extract()` returns
`account_charges: []` even though every chunk's X-Ray output is correct.

Run after `compile_workflow.py` and before any live ingest. Failing here
costs nothing; failing after a 5–15 minute ingest costs quota and time.

Usage:
    python validate_workflow_json.py workflow.json

Exits 0 if the JSON has the full expected shape. Exits 1 with explicit
error messages otherwise.

Validated:
    - top-level: `extract` and `steps` dicts present
    - `steps`: all 7 `WorkflowSteps` slot keys present (may be null):
      chunk-instruct, chunk-keys, chunk-summary, doc-keys, doc-summary,
      sect-instruct, sect-summary
    - each non-null step: all 6 `WorkflowStep` variant keys present
      (may be null): all, figure, paragraph, json, table, table-figure
    - at least one of `chunk-instruct` or `chunk-keys` is non-null
      (otherwise no extraction will run)
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

    ci = steps.get("chunk-instruct")
    ck = steps.get("chunk-keys")
    if ci is None and ck is None:
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
