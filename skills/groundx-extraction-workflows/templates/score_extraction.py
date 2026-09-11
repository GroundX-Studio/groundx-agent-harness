"""
score_extraction.py — compare extraction JSON against mapped expected-answer JSON.

Usage:
    python score_extraction.py output.json expected_answers.json

Domain-agnostic comparison
--------------------------
The comparator discovers structure from the data, not from hardcoded group
names: scalar expected-answer fields are compared as singleton (per-document) fields;
list-valued keys are compared as repeating record groups. Records are paired by
best field overlap (no per-domain match key required). Group names are aligned
across the expected-answer JSON and the extraction, with a small alias map for
known renames (e.g. expected-answer `charges` ↔ runner `account_charges`).

Null-vs-miss
------------
A field the expected-answer JSON leaves null is distinguished from an extraction miss:
  - expected null + extracted null    → PASS (correct null)
  - expected null + extracted a value  → WARN (value present; key null) — NOT a
    failure (e.g. customer_account_id: extract the printed value anyway)
  - expected a value + extracted null  → FAIL (missing)

Expected-answer format: JSON in the runner's output shape — scalar keys → singleton
(per-document) fields (null kept, so null-vs-miss can be scored), list-valued
keys → record groups. Convert or map spreadsheets, documents, text files, PDFs,
or human-review notes to this shape before scoring.

Output is a structured pass/warn/fail report with per-group accuracy. Exit code
is 0 if no field fails (warnings allowed), 1 otherwise.
"""

import csv
import argparse
import hashlib
import json
import os
import re
import sys
import typing
import unicodedata
from collections import Counter
from pathlib import Path


# ── normalization ──────────────────────────────────────────────────────────

# Group-name aliases: expected-answer group name → names it may appear under in the
# extraction. Mirrors the field-alias pattern; Component 5 (final_value renames)
# will generalize this into the YAML.
_GROUP_ALIASES: typing.Dict[str, typing.List[str]] = {
    "charges": ["charges", "account_charges"],
    "account_charges": ["account_charges", "charges"],
}
_FIELD_VALUE_OBJECT_KEYS = {"value", "_raw_text", "_confidence"}


def _is_field_value_object(value: typing.Any) -> bool:
    return (
        isinstance(value, dict)
        and "value" in value
        and set(value).issubset(_FIELD_VALUE_OBJECT_KEYS)
    )


def _field_value(value: typing.Any) -> typing.Any:
    if _is_field_value_object(value):
        return value.get("value")
    return value


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"\s*&\s*", " & ", normalized)
    normalized = re.sub(
        r"(?<=\d)\s+percent(?![\w-])",
        "%",
        normalized,
        flags=re.IGNORECASE,
    )
    return " ".join(normalized.split())


def normalize_value(val: typing.Any) -> str:
    """Normalize harmless text presentation and date syntax for comparison."""
    val = _field_value(val)
    if val is None:
        return ""
    s = _normalize_text(str(val))
    if "/" in s and len(s) <= 10:
        parts = s.split("/")
        if len(parts) == 3:
            m, d, y = parts
            if len(y) == 4 and m.isdigit() and d.isdigit():
                s = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return s


def _parsed_json_container(value: str) -> typing.Any:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _canonical_json_value(value: typing.Any) -> typing.Any:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, str):
        return ("string", normalize_value(value).casefold())
    if isinstance(value, list):
        return ("array", tuple(_canonical_json_value(item) for item in value))
    if isinstance(value, dict):
        return (
            "object",
            tuple(
                sorted(
                    (
                        unicodedata.normalize("NFC", str(key)),
                        _canonical_json_value(item),
                    )
                    for key, item in value.items()
                )
            ),
        )
    return (type(value).__name__, value)


def _get_aliased(d: typing.Dict[str, typing.Any], key: str) -> typing.Any:
    # Field names in expected-answer JSON are expected to match the extraction's
    # field names (both derive from the YAML). No client-specific bridging.
    if key in d:
        return d.get(key, "")
    if "." not in key:
        return ""
    current: typing.Any = d
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return ""
        current = current.get(part)
    return current


def _resolve_group(extracted: typing.Dict[str, typing.Any], group_name: str) -> typing.List[dict]:
    """Find the extracted record list for an expected-answer group, honoring aliases."""
    for alias in _GROUP_ALIASES.get(group_name, [group_name]):
        value = extracted.get(alias)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


# ── expected-answer loader ──────────────────────────────────────────────────


def _empty_expected() -> typing.Dict[str, typing.Any]:
    """Normalized expected-answer structure: singleton fields + named record groups."""
    return {"singleton": {}, "groups": {}}


def load_answer_key_json(json_path: str) -> typing.Dict[str, typing.Any]:
    with open(json_path, "r") as f:
        data = json.load(f)
    expected = _empty_expected()
    for key, value in data.items():
        if isinstance(value, list):
            expected["groups"][key] = [r for r in value if isinstance(r, dict)]
        elif _is_field_value_object(value):
            expected["singleton"][key] = value.get("value")
        elif isinstance(value, dict):
            # Nested object: treat its scalars as namespaced singleton fields.
            for sub_key, sub_val in value.items():
                if _is_field_value_object(sub_val):
                    expected["singleton"][f"{key}.{sub_key}"] = sub_val.get("value")
                elif not isinstance(sub_val, (list, dict)):
                    expected["singleton"][f"{key}.{sub_key}"] = sub_val
        else:
            # Scalar — keep even when null so null-vs-miss can be checked.
            expected["singleton"][key] = value
    return expected


def load_answer_key(path: str) -> typing.Dict[str, typing.Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return load_answer_key_json(path)
    raise ValueError(
        f"unsupported expected-answer extension: {ext} (expected .json). "
        "Map spreadsheets, documents, text files, PDFs, or human-review notes "
        "to the runner's JSON output shape first."
    )


# ── comparators ────────────────────────────────────────────────────────────


def _numeric_match(a: str, b: str) -> typing.Optional[bool]:
    try:
        return abs(float(a) - float(b)) < 0.01
    except (ValueError, TypeError):
        return None


def compare_field(exp_val: typing.Any, ext_val: typing.Any, *, unordered_array: bool = False) -> str:
    """Compare one field's expected vs extracted value with null-vs-miss semantics."""
    exp_norm = normalize_value(exp_val)
    ext_norm = normalize_value(ext_val)

    if exp_norm == "":
        # Expected-answer JSON has no value for this field.
        if ext_norm == "":
            return "PASS"  # correct null
        return "WARN (value; key null)"  # extracted a value the key leaves null
    if ext_norm == "":
        return "FAIL (missing)"

    exp_unwrapped, ext_unwrapped = _field_value(exp_val), _field_value(ext_val)
    exp_json = exp_unwrapped if isinstance(exp_unwrapped, (dict, list)) else _parsed_json_container(exp_norm)
    ext_json = ext_unwrapped if isinstance(ext_unwrapped, (dict, list)) else _parsed_json_container(ext_norm)
    if exp_json is not None and ext_json is not None:
        if unordered_array and isinstance(exp_json, list) and isinstance(ext_json, list):
            expected_members = Counter(map(_canonical_json_value, exp_json))
            actual_members = Counter(map(_canonical_json_value, ext_json))
            return "PASS" if expected_members == actual_members else "FAIL"
        return (
            "PASS"
            if _canonical_json_value(exp_json) == _canonical_json_value(ext_json)
            else "FAIL"
        )

    numeric = _numeric_match(exp_norm, ext_norm)
    if numeric is True:
        return "PASS"
    if numeric is False:
        return "FAIL"
    if exp_norm.lower() == ext_norm.lower():
        return "PASS" if exp_norm == ext_norm else "WARN (casing)"
    return "FAIL"


def _digest(value: typing.Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _expected_paths(expected: dict) -> set[str]:
    paths: set[str] = set()

    def visit(value, path):
        paths.add(path)
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for child in value:
                visit(child, path + "[]")
    for path, value in expected.get("singleton", {}).items():
        visit(value, path)
    for group, records in expected.get("groups", {}).items():
        visit(records, group)
    return paths


def validate_comparison_policy(policy: typing.Any, expected: dict | None = None) -> dict | None:
    if policy is None:
        return None
    if not isinstance(policy, dict) or set(policy) != {"version", "profiles", "fields"} or type(policy["version"]) is not int or policy["version"] != 1:
        raise ValueError("comparison policy requires version 1, profiles and fields")
    profiles, fields = policy["profiles"], policy["fields"]
    if not isinstance(profiles, dict) or not profiles or not isinstance(fields, dict) or not fields:
        raise ValueError("comparison profiles and fields must be nonempty objects")
    for name, profile in profiles.items():
        if not isinstance(name, str) or not name or not isinstance(profile, dict):
            raise ValueError("invalid comparison profile")
        kind = profile.get("kind")
        if kind == "equivalence" and set(profile) == {"kind", "values"}:
            values = profile["values"]
            if not isinstance(values, dict) or not values:
                raise ValueError("equivalence profile requires canonical values")
            seen = {}
            for canonical, aliases in values.items():
                if not isinstance(canonical, str) or not canonical.strip() or not isinstance(aliases, list) or not aliases:
                    raise ValueError("canonical values require nonempty string aliases")
                for alias in [canonical, *aliases]:
                    if not isinstance(alias, str) or not alias.strip():
                        raise ValueError("aliases must be nonempty strings")
                    token = _normalize_text(alias).casefold()
                    if token in seen and seen[token] != canonical:
                        raise ValueError("ambiguous comparison alias")
                    seen[token] = canonical
        elif kind == "source_review" and set(profile) == {"kind", "criterion"}:
            if not isinstance(profile["criterion"], str) or not profile["criterion"].strip():
                raise ValueError("source review requires a criterion")
        else:
            raise ValueError("unknown or malformed comparison profile")
    known = _expected_paths(expected) if expected is not None else None
    for path, profile in fields.items():
        if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z_][\w-]*(?:\[\])?(?:\.[A-Za-z_][\w-]*(?:\[\])?)*", path):
            raise ValueError("invalid comparison field path")
        if not isinstance(profile, str) or profile not in profiles:
            raise ValueError("unknown comparison profile")
        if known is not None and path not in known:
            raise ValueError(f"unknown comparison field: {path}")
    return policy


def _verify_review_context(context):
    """Verify cited physical pages and definitions against local source bytes."""
    if not isinstance(context, dict) or set(context) - {"sources", "field_definitions", "definition_source"}:
        raise ValueError("invalid review context")
    sources, definitions = context.get("sources", []), context.get("field_definitions", {})
    if not isinstance(sources, list) or not isinstance(definitions, dict):
        raise ValueError("invalid review evidence")
    verified = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"sha256", "page", "reference"} or type(source.get("page")) is not int or source["page"] < 1:
            raise ValueError("source requires SHA256, positive physical page and reference")
        reference = source.get("reference")
        if not isinstance(reference, str) or not Path(reference).is_file():
            raise ValueError("review source file is missing")
        if reference not in verified:
            from pypdf import PdfReader
            verified[reference] = (hashlib.sha256(Path(reference).read_bytes()).hexdigest(), len(PdfReader(reference).pages))
        digest, count = verified[reference]
        if source["sha256"] != digest or source["page"] > count:
            raise ValueError("review source hash or physical page does not match")
    if not definitions:
        if context.get("definition_source"):
            raise ValueError("definition source has no field definitions")
        return
    if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in definitions.items()):
        raise ValueError("field definitions must be nonempty strings")
    origin = context.get("definition_source")
    if not isinstance(origin, dict) or set(origin) != {"reference", "sha256", "fields"} or not isinstance(origin["reference"], str):
        raise ValueError("field definitions require their source YAML")
    path = Path(origin["reference"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != origin["sha256"]:
        raise ValueError("field definition source hash does not match")
    if not isinstance(origin["fields"], dict) or set(origin["fields"]) != set(definitions):
        raise ValueError("field definition paths do not match")
    import yaml
    document = yaml.safe_load(path.read_text())
    for field, tokens in origin["fields"].items():
        if not isinstance(tokens, list) or not tokens or any(not isinstance(t, str) for t in tokens):
            raise ValueError("field definition path must contain YAML keys")
        value = document
        for token in tokens:
            if not isinstance(value, dict) or token not in value:
                raise ValueError("field definition path is missing")
            value = value[token]
        if value != definitions[field]:
            raise ValueError("field definition does not match source YAML")


class _ComparisonPolicy:
    """Deterministic comparison and separately bound, post-pairing source reviews."""

    def __init__(self, policy, expected, extracted, context=None, decisions=None):
        self.policy = validate_comparison_policy(policy, expected)
        self.context = context or {}
        _verify_review_context(self.context)
        self.binding = {"policy_sha256": _digest(policy), "expected_sha256": _digest(expected), "extracted_sha256": _digest(extracted), "context_sha256": _digest(self.context)}
        self.decisions = {}
        self.used = set()
        self.packets = {}
        self.pending = set()
        if decisions is not None:
            if not isinstance(decisions, dict) or set(decisions) != {"version", "decisions"} or type(decisions["version"]) is not int or decisions["version"] != 1 or not isinstance(decisions["decisions"], list):
                raise ValueError("invalid source review decisions")
            for decision in decisions["decisions"]:
                if not isinstance(decision, dict) or set(decision) != {"packet_sha256", "decision", "reviewer", "rationale", "citations"}:
                    raise ValueError("malformed source review decision")
                key = decision["packet_sha256"]
                reviewer = decision["reviewer"]
                if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key) or key in self.decisions or decision["decision"] not in ("equivalent", "wrong", "unresolved"):
                    raise ValueError("invalid or duplicate review decision")
                if not isinstance(reviewer, dict) or set(reviewer) != {"id", "version"} or any(not isinstance(v, str) or not v.strip() for v in reviewer.values()) or not isinstance(decision["rationale"], str) or not decision["rationale"].strip() or not isinstance(decision["citations"], list):
                    raise ValueError("reviewer identity, version, rationale and citations are required")
                self.decisions[key] = decision

    def transform(self, value, path):
        value = _field_value(value)
        if isinstance(value, dict):
            return {k: self.transform(v, path + "." + k) for k, v in value.items()}
        if isinstance(value, list):
            return [self.transform(v, path + "[]") for v in value]
        profile = self.policy["profiles"].get(self.policy["fields"].get(path), {})
        if isinstance(value, str) and profile.get("kind") == "equivalence":
            token = _normalize_text(value).casefold()
            for canonical, aliases in profile["values"].items():
                if any(token == _normalize_text(alias).casefold() for alias in [canonical, *aliases]):
                    return canonical
        return value

    def affects(self, path):
        return any(p == path or p.startswith(path + ".") or p.startswith(path + "[]") for p in self.policy["fields"])

    def compare(self, expected, actual, path, *, location=None, unordered=False):
        before = compare_field(expected, actual, unordered_array=unordered)
        transformed_expected = self.transform(expected, path)
        transformed_actual = self.transform(actual, path)
        status = compare_field(transformed_expected, transformed_actual, unordered_array=unordered)
        reviews = []
        if status.startswith("FAIL") and location is not None:
            status, reviews = self._review(expected, actual, path, location, unordered)
        return status, {"raw_status": before, "comparison_path": path, "policy_sha256": self.binding["policy_sha256"], "reviews": reviews}

    def _review(self, expected, actual, path, location, unordered=False, nested=False):
        left, right = self.transform(expected, path), self.transform(actual, path)
        deterministic = compare_field([left], [right]) if nested else compare_field(left, right, unordered_array=unordered)
        if not deterministic.startswith("FAIL"):
            return deterministic, []
        # Reviews do not change cardinality, types, missing values or pairing.
        if isinstance(expected, dict) and isinstance(actual, dict) and set(expected) == set(actual):
            outcomes = [self._review(v, actual[k], path + "." + k, location + "." + k, nested=True) for k, v in expected.items()]
        elif isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual) and not unordered:
            outcomes = [self._review(e, a, path + "[]", location + f"[{i}]", nested=True) for i, (e, a) in enumerate(zip(expected, actual))]
        else:
            outcomes = None
        if outcomes is not None:
            return ("PASS" if all(not s.startswith("FAIL") for s, _ in outcomes) else "FAIL",
                    [r for _, entries in outcomes for r in entries])
        name = self.policy["fields"].get(path)
        profile = self.policy["profiles"].get(name, {})
        if profile.get("kind") != "source_review" or not isinstance(expected, str) or not expected.strip() or not isinstance(actual, str) or not actual.strip():
            return deterministic, []
        definition = self.context.get("field_definitions", {}).get(path)
        sources = self.context.get("sources", [])
        packet = {**self.binding, "path": path, "location": location, "profile": name,
                  "criterion": profile["criterion"], "field_definition": definition,
                  "expected": expected, "extracted": actual, "sources": sources,
                  "reviewable": bool(definition and sources)}
        key = _digest(packet)
        packet["packet_sha256"] = key
        self.packets[key] = packet
        decision = self.decisions.get(key)
        if decision is None:
            self.pending.add(key)
            return "FAIL (review required)", [{"packet_sha256": key, "decision": "unresolved"}]
        self.used.add(key)
        allowed = {(s["sha256"], s["page"]) for s in sources}
        citations = decision["citations"]
        if not packet["reviewable"] or not citations or any(not isinstance(c, dict) or set(c) != {"sha256", "page"} or type(c["page"]) is not int or (c["sha256"], c["page"]) not in allowed for c in citations):
            raise ValueError("review lacks matching source evidence")
        if decision["decision"] == "unresolved":
            self.pending.add(key)
        return ("PASS" if decision["decision"] == "equivalent" else "FAIL"), [decision]

    def finish(self):
        if set(self.decisions) != self.used:
            raise ValueError("stale or unmatched review decisions")
        return {**self.binding, "policy": self.policy, "pending_reviews": len(self.pending),
                "review_packets": list(self.packets.values()), "decisions": list(self.decisions.values())}

def _accepted_value_paths(expected: typing.Dict[str, typing.Any]) -> set[str]:
    paths = set((expected.get("singleton") or {}).keys())
    for group_name, records in (expected.get("groups") or {}).items():
        for record in records:
            if isinstance(record, dict):
                paths.update(f"{group_name}.{field}" for field in record)
    return paths


def validate_unordered_array_fields(
    fields: typing.Any,
    expected: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> frozenset[str]:
    """Validate explicit field paths without inferring semantics from field names."""
    if fields is None:
        return frozenset()
    if not isinstance(fields, (list, tuple, set, frozenset)):
        raise ValueError("unordered array fields must be a collection of field paths")
    if any(not isinstance(field, str) or not field.strip() for field in fields):
        raise ValueError("unordered array fields must contain non-empty paths")
    result = frozenset(fields)
    if len(result) != len(fields):
        raise ValueError("unordered array fields must not contain duplicates")
    if expected is not None and result - _accepted_value_paths(expected):
        raise ValueError("unordered array fields contain unknown expected paths")
    return result


def validate_accepted_values(
    accepted_values: typing.Optional[typing.Dict[str, typing.List[typing.Any]]],
    expected: typing.Dict[str, typing.Any],
) -> typing.Dict[str, typing.Tuple[typing.Any, ...]]:
    """Validate optional case-owned scalar alternatives against the answer key."""
    if accepted_values is None:
        return {}
    if not isinstance(accepted_values, dict):
        raise ValueError("accepted values must be an object")
    valid_paths = _accepted_value_paths(expected)
    validated: typing.Dict[str, typing.Tuple[typing.Any, ...]] = {}
    for path, alternatives in accepted_values.items():
        if not isinstance(path, str) or not path.strip():
            raise ValueError("accepted value field paths must be non-empty strings")
        if path not in valid_paths:
            raise ValueError(f"accepted value path {path!r} is an unknown expected field")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError(f"accepted values for {path!r} must be a non-empty array")
        if any(value is None or isinstance(value, (dict, list)) for value in alternatives):
            raise ValueError(f"accepted values for {path!r} must contain non-null scalars")
        validated[path] = tuple(alternatives)
    return validated


def _compare_field_with_accepted(
    exp_val: typing.Any,
    ext_val: typing.Any,
    alternatives: typing.Iterable[typing.Any] = (),
    *, unordered_array: bool = False,
) -> typing.Tuple[str, typing.Optional[typing.Any]]:
    status = compare_field(exp_val, ext_val, unordered_array=unordered_array)
    if not status.startswith("FAIL"):
        return status, None
    for alternative in alternatives:
        alternative_status = compare_field(alternative, ext_val, unordered_array=unordered_array)
        if not alternative_status.startswith("FAIL"):
            return alternative_status, alternative
    return status, None


def classify_field(
    exp_val: typing.Any,
    ext_val: typing.Any,
) -> typing.Tuple[str, typing.Optional[str]]:
    """Return (status, miss_type) for one field within a record.

    miss_type classifies why a field is not a clean extraction hit:
      - "expected-null":  the expected-answer JSON has no value here (informational, NOT
        an extraction target — excluded from the field-accuracy denominator).
      - "not-found":      key has a value; extraction produced nothing.
      - "field-mismatch": key has a value; extraction produced a different one.
      - None:             clean pass (exact or casing-only).
    """
    status = compare_field(exp_val, ext_val)
    if normalize_value(exp_val) == "":
        return status, "expected-null"
    if status in ("PASS", "WARN (casing)"):
        return status, None
    if normalize_value(ext_val) == "":
        return status, "not-found"
    return status, "field-mismatch"


def _classify_field_with_accepted(
    exp_val: typing.Any,
    ext_val: typing.Any,
    alternatives: typing.Iterable[typing.Any],
    *, unordered_array: bool = False,
) -> typing.Tuple[str, typing.Optional[str], typing.Optional[typing.Any]]:
    status, matched_accepted_value = _compare_field_with_accepted(
        exp_val,
        ext_val,
        alternatives,
        unordered_array=unordered_array,
    )
    if normalize_value(exp_val) == "":
        return status, "expected-null", matched_accepted_value
    if status in ("PASS", "WARN (casing)"):
        return status, None, matched_accepted_value
    if normalize_value(ext_val) == "":
        return status, "not-found", matched_accepted_value
    return status, "field-mismatch", matched_accepted_value


def compare_singleton(
    extracted: typing.Dict[str, typing.Any],
    expected_singleton: typing.Dict[str, typing.Any],
    accepted_values: typing.Optional[
        typing.Dict[str, typing.Tuple[typing.Any, ...]]
    ] = None,
    unordered_array_fields: frozenset[str] = frozenset(),
    comparison: _ComparisonPolicy | None = None,
) -> typing.List[dict]:
    accepted_values = accepted_values or {}
    results = []
    for field, exp_val in expected_singleton.items():
        ext_val = _get_aliased(extracted, field)
        status, matched_accepted_value = _compare_field_with_accepted(
            exp_val,
            ext_val,
            accepted_values.get(field, ()),
            unordered_array=field in unordered_array_fields,
        )
        result = {
            "field": field,
            "expected": exp_val,
            "extracted": ext_val if normalize_value(ext_val) != "" else "(empty)",
            "status": status,
        }
        if comparison is not None and comparison.affects(field):
            status, audit = comparison.compare(exp_val, ext_val, field, location=field, unordered=field in unordered_array_fields)
            result.update(audit)
            result["status"] = status
        if field in accepted_values:
            result["accepted_values"] = list(accepted_values[field])
        if matched_accepted_value is not None:
            result["matched_accepted_value"] = matched_accepted_value
        results.append(result)
    return results


def _record_overlap(
    exp_record: dict,
    ext_record: dict,
    *,
    group_name: str,
    accepted_values: typing.Dict[str, typing.Tuple[typing.Any, ...]],
    unordered_array_fields: frozenset[str] = frozenset(),
    comparison: _ComparisonPolicy | None = None,
) -> int:
    """How many of the expected record's fields match the extracted record."""
    score = 0
    for field, exp_val in exp_record.items():
        if normalize_value(exp_val) == "":
            continue
        status, _ = _compare_field_with_accepted(
            exp_val,
            _get_aliased(ext_record, field),
            accepted_values.get(f"{group_name}.{field}", ()),
            unordered_array=f"{group_name}.{field}" in unordered_array_fields,
        )
        if comparison is not None and comparison.affects(f"{group_name}[].{field}"):
            status, _ = comparison.compare(exp_val, _get_aliased(ext_record, field), f"{group_name}[].{field}", unordered=f"{group_name}.{field}" in unordered_array_fields)
        if status in ("PASS", "WARN (casing)"):
            score += 1
    return score


def _record_label(record: dict) -> str:
    for key in ("meter_number", "charge_description_as_printed", "chg_desc_1", "description", "desc", "id"):
        val = _get_aliased(record, key)
        if normalize_value(val):
            return str(val)
    # Fall back to the first non-empty value.
    for val in record.values():
        if normalize_value(val):
            return str(val)
    return "(record)"


def _empty_field_counts() -> typing.Dict[str, int]:
    return {"pass": 0, "scored": 0, "not_found": 0, "field_mismatch": 0, "expected_null": 0}


def compare_records(
    extracted_records: typing.List[dict],
    expected_records: typing.List[dict],
    *,
    group_name: str = "",
    accepted_values: typing.Optional[
        typing.Dict[str, typing.Tuple[typing.Any, ...]]
    ] = None,
    unordered_array_fields: frozenset[str] = frozenset(),
    comparison: _ComparisonPolicy | None = None,
) -> typing.Dict[str, typing.Any]:
    """Pair expected and extracted records by best field overlap, then score
    each field WITHIN the matched records — never all-or-nothing.

    Returns a dict with:
      - records:         per-record results (matched / not_found / extra), each
                         matched record carrying its per-field statuses + miss types.
      - field_breakdown: per field name, aggregated counts across the group's
                         records (pass / scored / not_found / field_mismatch /
                         expected_null). Field accuracy = pass / scored; nulls
                         are excluded from `scored`.
      - record_summary:  matched / expected / extra / not_found record counts.
      - field_summary:   (passed, scored) across the whole group.
    """
    accepted_values = accepted_values or {}
    records_out: typing.List[dict] = []
    field_breakdown: typing.Dict[str, typing.Dict[str, int]] = {}
    used: set[int] = set()
    matched = not_found = 0

    def bump(field: str, key: str) -> None:
        field_breakdown.setdefault(field, _empty_field_counts())[key] += 1

    for expected_index, exp_record in enumerate(expected_records):
        best_idx = -1
        best_score = 0
        for idx, ext_record in enumerate(extracted_records):
            if idx in used:
                continue
            score = _record_overlap(
                exp_record,
                ext_record,
                group_name=group_name,
                accepted_values=accepted_values,
                unordered_array_fields=unordered_array_fields,
                comparison=comparison,
            )
            if score > best_score:
                best_score = score
                best_idx = idx

        label = _record_label(exp_record)
        if best_idx < 0 or best_score == 0:
            not_found += 1
            # Every value the key specified is a not-found field on this record.
            for field, exp_val in exp_record.items():
                if normalize_value(exp_val) == "":
                    bump(field, "expected_null")
                else:
                    bump(field, "scored")
                    bump(field, "not_found")
            records_out.append({
                "label": label,
                "match": "not_found",
                "details": f"Expected: {json.dumps(exp_record, sort_keys=True, default=str)}",
            })
            continue

        used.add(best_idx)
        matched += 1
        match = extracted_records[best_idx]
        fields: typing.List[dict] = []
        record_ok = True
        for field, exp_val in exp_record.items():
            ext_val = _get_aliased(match, field)
            field_path = f"{group_name}.{field}"
            status, miss_type, matched_accepted_value = _classify_field_with_accepted(
                exp_val,
                ext_val,
                accepted_values.get(field_path, ()),
                unordered_array=field_path in unordered_array_fields,
            )
            audit = {}
            if comparison is not None and comparison.affects(f"{group_name}[].{field}"):
                status, audit = comparison.compare(exp_val, ext_val, f"{group_name}[].{field}", location=f"{group_name}[expected={expected_index},extracted={best_idx}].{field}", unordered=field_path in unordered_array_fields)
                if miss_type != "expected-null":
                    miss_type = None if not status.startswith("FAIL") else ("not-found" if normalize_value(ext_val) == "" else "field-mismatch")
            if miss_type == "expected-null":
                bump(field, "expected_null")
            else:
                bump(field, "scored")
                if miss_type is None:
                    bump(field, "pass")
                else:
                    bump(field, miss_type.replace("-", "_"))
                    record_ok = False
            field_result = {
                "field": field,
                "expected": exp_val,
                "extracted": ext_val if normalize_value(ext_val) != "" else "(empty)",
                "status": status,
                "miss_type": miss_type,
                **audit,
            }
            if field_path in accepted_values:
                field_result["accepted_values"] = list(accepted_values[field_path])
            if matched_accepted_value is not None:
                field_result["matched_accepted_value"] = matched_accepted_value
            fields.append(field_result)
        records_out.append({
            "label": label,
            "match": "matched",
            "record_status": "PASS" if record_ok else "FAIL",
            "fields": fields,
        })

    extra = 0
    for idx, ext_record in enumerate(extracted_records):
        if idx not in used:
            extra += 1
            records_out.append({
                "label": _record_label(ext_record),
                "match": "extra",
                "details": "Not in expected-answer JSON",
            })

    passed = sum(c["pass"] for c in field_breakdown.values())
    scored = sum(c["scored"] for c in field_breakdown.values())
    return {
        "records": records_out,
        "field_breakdown": field_breakdown,
        "record_summary": {
            "matched": matched,
            "expected": len(expected_records),
            "extra": extra,
            "not_found": not_found,
        },
        "field_summary": (passed, scored),
    }


def compare_extraction(
    extracted: typing.Dict[str, typing.Any],
    expected: typing.Dict[str, typing.Any],
    *,
    accepted_values: typing.Optional[typing.Dict[str, typing.List[typing.Any]]] = None,
    unordered_array_fields: typing.Optional[typing.Iterable[str]] = None,
    comparison_policy: dict | None = None,
    review_context: dict | None = None,
    review_decisions: dict | None = None,
) -> typing.Dict[str, typing.Any]:
    """Compare an extraction dict against normalized expected-answer structure.

    Returns a report: per-field singleton results, per-group record results, a
    summary of (pass, total) per section, and an overall has_failure flag.
    """
    validated_accepted_values = validate_accepted_values(accepted_values, expected)
    validated_unordered_fields = validate_unordered_array_fields(unordered_array_fields, expected)
    comparison = _ComparisonPolicy(comparison_policy, expected, extracted, review_context, review_decisions) if comparison_policy is not None else None
    if comparison is None and (review_context is not None or review_decisions is not None):
        raise ValueError("review inputs require a comparison policy")
    if comparison is not None:
        configured = {p.replace("[]", "") for p in comparison.policy["fields"]}
        if configured & (set(validated_accepted_values) | set(validated_unordered_fields)):
            raise ValueError("comparison profile conflicts with an existing field comparison setting")
    singleton_results = compare_singleton(
        extracted,
        expected.get("singleton") or {},
        validated_accepted_values,
        validated_unordered_fields,
        comparison,
    )

    group_results: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    group_summary: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    group_has_failure = False
    for group_name, exp_records in (expected.get("groups") or {}).items():
        ext_records = _resolve_group(extracted, group_name)
        gr = compare_records(
            ext_records,
            exp_records,
            group_name=group_name,
            accepted_values=validated_accepted_values,
            unordered_array_fields=validated_unordered_fields,
            comparison=comparison,
        )
        group_results[group_name] = gr
        rs = gr["record_summary"]
        group_summary[group_name] = {
            "records": (rs["matched"], rs["expected"]),
            "fields": gr["field_summary"],
            "extra": rs["extra"],
        }
        if rs["not_found"] or any(
            c["not_found"] or c["field_mismatch"] for c in gr["field_breakdown"].values()
        ):
            group_has_failure = True

    singleton_pass = sum(1 for r in singleton_results if r["status"] in ("PASS", "WARN (casing)", "WARN (value; key null)"))
    has_failure = group_has_failure or any(
        r["status"].startswith("FAIL") for r in singleton_results
    )

    result = {
        "singleton": singleton_results,
        "groups": group_results,
        "summary": {
            "singleton": (singleton_pass, len(singleton_results)),
            "groups": group_summary,
        },
        "has_failure": has_failure,
    }
    if comparison is not None:
        result["comparison"] = comparison.finish()
        if result["comparison"]["pending_reviews"]:
            result["has_failure"] = True
    return result


# ── scoring-input helpers (expected-answer JSON + manifest resolution) ──────


def load_manifest(path: typing.Optional[str]) -> typing.Dict[str, typing.Dict[str, str]]:
    """Parse a manifest CSV (a `filename` column + any dimension columns such as
    `vendor`/`service_type`) into {doc_base: {dimension: value}}. Empty if absent."""
    if not path or not os.path.isfile(path):
        return {}
    out: typing.Dict[str, typing.Dict[str, str]] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            fname = (row.get("filename") or "").strip()
            if not fname:
                continue
            base = os.path.splitext(os.path.basename(fname))[0]
            out[base] = {k: v for k, v in row.items() if k != "filename" and v}
    return out


def find_answer_key(keys_dir: str, doc_base: str) -> typing.Optional[str]:
    """Resolve a document's expected-answer JSON by base name."""
    for cand in (f"{doc_base}.json", f"{doc_base}.answer.json", f"{doc_base}.answer_key.json"):
        p = os.path.join(keys_dir, cand)
        if os.path.isfile(p):
            return p
    return None


# ── reporting ──────────────────────────────────────────────────────────────


def _icon(status: str) -> str:
    if status == "PASS":
        return "PASS"
    if status.startswith("WARN"):
        return "WARN"
    return "FAIL"


def load_scoring_options(policy_path=None, context_path=None, decisions_path=None) -> dict:
    options = {}
    for name, path in (("comparison_policy", policy_path), ("review_context", context_path), ("review_decisions", decisions_path)):
        if path is not None:
            with open(path) as stream:
                options[name] = json.load(stream)
    return options


def main(argv: typing.List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction")
    parser.add_argument("expected_answers")
    parser.add_argument("--comparison-policy")
    parser.add_argument("--review-context")
    parser.add_argument("--review-decisions")
    parser.add_argument("--report-json")
    args = parser.parse_args(argv[1:])
    extract_path, key_path = args.extraction, args.expected_answers
    if not os.path.isfile(extract_path):
        print(f"ERROR: extraction JSON not found: {extract_path}", file=sys.stderr)
        return 2
    if not os.path.isfile(key_path):
        print(f"ERROR: expected-answer JSON not found: {key_path}", file=sys.stderr)
        return 2

    with open(extract_path, "r") as f:
        extracted = json.load(f)

    expected = load_answer_key(key_path)
    report = compare_extraction(extracted, expected, **load_scoring_options(args.comparison_policy, args.review_context, args.review_decisions))
    if args.report_json:
        with open(args.report_json, "w") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")

    print("=" * 60)
    print("EXTRACTX COMPARISON")
    print("=" * 60)
    group_desc = ", ".join(
        f"{n}={len(v)}" for n, v in (expected.get("groups") or {}).items()
    ) or "(none)"
    print(f"expected-answer JSON: {len(expected['singleton'])} singleton fields, groups: {group_desc}")

    print("\n" + "-" * 60)
    print("SINGLETON FIELDS")
    print("-" * 60)
    for r in report["singleton"]:
        print(f"  [{_icon(r['status'])}] {r['field']}: {r['status']}")
        if r["status"].startswith("FAIL"):
            print(f"       expected:  {r['expected']}")
            print(f"       extracted: {r['extracted']}")
    sp, st = report["summary"]["singleton"]
    print(f"\nsingleton: {sp}/{st} passed")

    for group_name, gr in report["groups"].items():
        print("\n" + "-" * 60)
        print(group_name.upper())
        print("-" * 60)
        for r in gr["records"]:
            if r["match"] == "matched":
                print(f"  [{_icon(r['record_status'])}] {r['label']}: {r['record_status']}")
                for f in r["fields"]:
                    if f["miss_type"] in ("not-found", "field-mismatch"):
                        print(f"       {f['field']}: expected '{f['expected']}' "
                              f"got '{f['extracted']}' [{f['miss_type']}]")
            elif r["match"] == "not_found":
                print(f"  [FAIL] {r['label']}: not found in extraction")
            else:
                print(f"  [WARN] {r['label']}: extra (not in expected-answer JSON)")

        print(f"\n  per-field accuracy ({group_name}):")
        for fname, c in sorted(gr["field_breakdown"].items()):
            if not c["scored"]:
                continue
            extra = ""
            if c["pass"] < c["scored"]:
                extra = f"  [{c['not_found']} not-found, {c['field_mismatch']} mismatch]"
            print(f"    {fname}: {c['pass']}/{c['scored']} ({c['pass'] / c['scored']:.0%}){extra}")

        gs = report["summary"]["groups"][group_name]
        fp, ft = gs["fields"]
        rm, re_ = gs["records"]
        print(f"\n{group_name}: {fp}/{ft} fields, {rm}/{re_} records matched, {gs['extra']} extra")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  singleton fields: {sp}/{st}")
    for group_name, gs in report["summary"]["groups"].items():
        fp, ft = gs["fields"]
        rm, re_ = gs["records"]
        pct = f" ({fp / ft:.0%})" if ft else ""
        print(f"  {group_name}: {fp}/{ft} fields{pct}, {rm}/{re_} records")

    return 1 if report["has_failure"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
