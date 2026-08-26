"""Small, non-authoritative readers for authored extraction YAML.

Cashbot owns validation and compilation. This module reads only the source data
needed by offline Harness tools. It never derives execution metadata.
"""

from __future__ import annotations

from pathlib import Path
import typing

import yaml


_RESERVED_TOP_LEVEL = {
    "extraction_policy_version",
    "workflow",
    "groups",
}
def load_workflow_source(path: str | Path) -> dict[str, typing.Any]:
    """Load authored YAML as a mapping without validation or compilation."""
    source_path = Path(path)
    payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{source_path}: workflow source must be a mapping")
    return typing.cast(dict[str, typing.Any], payload)


def _final_groups(source: dict[str, typing.Any]) -> typing.Iterator[tuple[str, dict[str, typing.Any]]]:
    for name, value in source.items():
        if name in _RESERVED_TOP_LEVEL or name.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(value.get("fields"), dict):
            yield name, typing.cast(dict[str, typing.Any], value)


def _definition_fields(source: dict[str, typing.Any], name: str) -> dict[str, typing.Any]:
    definitions = source.get("_defs")
    if not isinstance(definitions, dict):
        return {}
    definition = definitions.get(name)
    if not isinstance(definition, dict):
        return {}
    fields = definition.get("fields", definition)
    return typing.cast(dict[str, typing.Any], fields) if isinstance(fields, dict) else {}


def source_yaml_field_names(source: dict[str, typing.Any], source_name: str = "<yaml>") -> set[str]:
    """Return authored final-field names for field-coverage checks."""
    del source_name
    names: set[str] = set()
    for _, group in _final_groups(source):
        includes = group.get("include", [])
        if isinstance(includes, str):
            includes = [includes]
        if isinstance(includes, list):
            for include in includes:
                if isinstance(include, str):
                    names.update(_definition_fields(source, include))
        fields = group.get("fields")
        if isinstance(fields, dict):
            names.update(str(name) for name in fields)
    return names
