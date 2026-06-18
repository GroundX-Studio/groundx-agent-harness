"""
check_field_coverage.py — fitness gate for customer-intake authoring.

Before the first extraction run, the authored prompt.yaml must cover the
customer's field catalog: every catalog field name must appear as a field in
the YAML (YAML fields ⊇ catalog fields). A missing field means the extraction
will silently omit something the customer asked for.

Usage:
    python check_field_coverage.py prompt.yaml catalog.json
    python check_field_coverage.py prompt.yaml catalog.csv

Catalog shapes:
  - JSON: a list of field-name strings (["account_number", "total_due"]),
    or a list of objects each carrying a "field"/"name"/"field_name" key.
  - CSV: the first column is the field name; a header row named
    field/name/field_name is skipped.

The gate is one-directional: extra YAML fields beyond the catalog are allowed
(see references/13_customer_intake.md §5). A field renamed for downstream output
is handled by the comparison alias map, not by dropping the field.

Exit code 0 when every catalog field is covered, 1 when any field is missing.
Standard library only (plus PyYAML, already a runner dependency).
"""

import csv
import json
import sys
import typing

import yaml

import compile_workflow


def yaml_field_names(doc: typing.Any) -> typing.Set[str]:
    """Collect final field keys after compiler source validation."""
    return compile_workflow.source_yaml_field_names(doc)


def _catalog_from_json(data: typing.Any) -> typing.List[str]:
    if not isinstance(data, list):
        raise ValueError("JSON catalog must be a list of field names or objects")
    names: typing.List[str] = []
    for item in data:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            for key in ("field", "name", "field_name"):
                if key in item:
                    names.append(str(item[key]))
                    break
            else:
                raise ValueError(
                    f"catalog object missing a field/name/field_name key: {item!r}"
                )
        else:
            raise ValueError(f"unsupported catalog entry: {item!r}")
    return names


def _catalog_from_csv(text: str) -> typing.List[str]:
    rows = list(csv.reader(text.splitlines()))
    names: typing.List[str] = []
    for i, row in enumerate(rows):
        if not row or not row[0].strip():
            continue
        cell = row[0].strip()
        if i == 0 and cell.lower() in ("field", "name", "field_name"):
            continue  # header row
        names.append(cell)
    return names


def catalog_field_names(path: str) -> typing.List[str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith(".json"):
        return _catalog_from_json(json.loads(text))
    return _catalog_from_csv(text)


def missing_fields(yaml_path: str, catalog_path: str) -> typing.List[str]:
    """Catalog field names not covered by the YAML, in catalog order, de-duped."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    covered = yaml_field_names(doc)
    missing: typing.List[str] = []
    seen: typing.Set[str] = set()
    for name in catalog_field_names(catalog_path):
        if name not in covered and name not in seen:
            missing.append(name)
            seen.add(name)
    return missing


def main(argv: typing.List[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: python check_field_coverage.py prompt.yaml catalog.{json,csv}",
              file=sys.stderr)
        return 2
    yaml_path, catalog_path = argv[1], argv[2]
    missing = missing_fields(yaml_path, catalog_path)
    if missing:
        print(f"FAIL: {len(missing)} catalog field(s) not covered by {yaml_path}:")
        for name in missing:
            print(f"  - {name}")
        print("Add each to the right group or confirm with the owner that it is "
              "out of scope (references/13_customer_intake.md §5).")
        return 1
    print(f"PASS: all catalog fields are covered by {yaml_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
