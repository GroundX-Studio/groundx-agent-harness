#!/usr/bin/env python3
"""business_logic.py — declarative, client-side post-extraction business logic.

Runs AFTER the runner aggregates X-Ray chunk output into an extract dict shaped
like `{<singleton scalar fields>, "account_charges": [...], "meters": [...]}`
(see `xray_to_extract.py`). The GroundX platform extracts records; it does not
dedup them, link them across groups, surface their conflicts, or copy parent
fields onto children. Customers need that, so this module supplies a small set
of declarative primitives driven by per-group YAML metadata.

Stdlib-only. Pure functions, no API calls. Normalization is consistent with
`templates/score_extraction.py` (strip + case-insensitive) so a record judged a duplicate
or a foreign-key match here matches the comparator's notion of equality.

Metadata vocabulary (per-group, all optional)
----------------------------------------------
  unique_attrs   list[str]   Records that share normalized values of these
                             fields are duplicates. Keep the first; merge any
                             non-null fields from the dropped duplicates onto it.
  match_attrs    list[str]   Cross-group foreign key. Links this (child) group's
                             records to a record in a parent group sharing the
                             same normalized values of these fields.
  conflict_attrs list[str]   When linked/deduped records disagree on these
                             fields, surface every distinct value as
                             `<field>__conflicts: [values]` instead of silently
                             picking one.
  passthrough    {"from": "<parent_group>", "fields": [...]}
                             Copy those fields from the linked parent record onto
                             each child record.

`apply_business_logic(doc, group_metadata)` is the orchestrator. It is a no-op
when `group_metadata` is empty/absent, so a YAML carrying none of these keys
produces unchanged output.

The "primitive gap": these primitives are intentionally small. If a customer
needs logic they cannot express (computed totals, conditional rollups,
multi-hop joins, unit conversions), do NOT fork this module per customer. Log
the gap and escalate — see `references/12_business_logic.md`.
"""

import typing


# ── normalization (consistent with score_extraction.normalize_value) ─────────────────


def normalize_value(val: typing.Any) -> str:
    """Strip + date-normalize a value for comparison. Mirrors score_extraction.py.

    Kept as a local copy so this module stays importable on its own (the runner
    imports siblings individually). The two must agree: a record this module
    treats as a duplicate should be a record the comparator treats as equal.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if "/" in s and len(s) <= 10:
        parts = s.split("/")
        if len(parts) == 3:
            m, d, y = parts
            if len(y) == 4 and m.isdigit() and d.isdigit():
                s = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return s


def _norm_key(record: dict, attrs: typing.List[str]) -> tuple:
    """Case-insensitive, normalized tuple key over `attrs` for matching."""
    return tuple(normalize_value(record.get(a)).lower() for a in attrs)


def _is_empty(val: typing.Any) -> bool:
    return normalize_value(val) == ""


# ── primitives ──────────────────────────────────────────────────────────────


def dedup(records: typing.List[dict], unique_attrs: typing.List[str]) -> typing.List[dict]:
    """Collapse records sharing normalized values of `unique_attrs`.

    Keeps the first record per key and merges any non-null fields from the
    dropped duplicates onto it (a later duplicate can fill a field the first
    record left empty). Order of first appearance is preserved. A no-op when
    `unique_attrs` is empty.
    """
    if not unique_attrs:
        return list(records)

    order: typing.List[tuple] = []
    by_key: typing.Dict[tuple, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = _norm_key(record, unique_attrs)
        if key not in by_key:
            by_key[key] = dict(record)
            order.append(key)
            continue
        # Merge non-null fields from the duplicate into the kept record.
        kept = by_key[key]
        for field, value in record.items():
            if _is_empty(kept.get(field)) and not _is_empty(value):
                kept[field] = value
    return [by_key[k] for k in order]


def link(
    child: typing.List[dict],
    parent: typing.List[dict],
    match_attrs: typing.List[str],
) -> typing.List[dict]:
    """Annotate each child record with the parent it matches on `match_attrs`.

    Returns new child records (originals untouched) each carrying a `_parent`
    key: the matched parent record, or None if no parent matches. A no-op
    (every `_parent` is None) when `match_attrs` is empty.
    """
    parents_by_key: typing.Dict[tuple, dict] = {}
    if match_attrs:
        for p in parent:
            if not isinstance(p, dict):
                continue
            key = _norm_key(p, match_attrs)
            # First parent wins on duplicate keys.
            parents_by_key.setdefault(key, p)

    annotated: typing.List[dict] = []
    for c in child:
        if not isinstance(c, dict):
            continue
        out = dict(c)
        if match_attrs:
            out["_parent"] = parents_by_key.get(_norm_key(c, match_attrs))
        else:
            out["_parent"] = None
        annotated.append(out)
    return annotated


def surface_conflicts(
    records: typing.List[dict],
    conflict_attrs: typing.List[str],
) -> typing.List[dict]:
    """Within a group of records that should agree, surface disagreements.

    For each field in `conflict_attrs`, if the records carry more than one
    distinct non-null normalized value, add `<field>__conflicts: [values]` to
    every record listing the distinct raw values (first-seen order). The
    original field is left as-is. A no-op when `conflict_attrs` is empty or the
    records all agree.
    """
    if not conflict_attrs or not records:
        return list(records)

    conflicts: typing.Dict[str, typing.List[typing.Any]] = {}
    for field in conflict_attrs:
        seen_norm: typing.List[str] = []
        raw_values: typing.List[typing.Any] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            value = record.get(field)
            if _is_empty(value):
                continue
            norm = normalize_value(value).lower()
            if norm not in seen_norm:
                seen_norm.append(norm)
                raw_values.append(value)
        if len(raw_values) > 1:
            conflicts[field] = raw_values

    if not conflicts:
        return list(records)

    out: typing.List[dict] = []
    for record in records:
        if not isinstance(record, dict):
            out.append(record)
            continue
        annotated = dict(record)
        for field, values in conflicts.items():
            annotated[f"{field}__conflicts"] = list(values)
        out.append(annotated)
    return out


def apply_passthrough(
    child: typing.List[dict],
    parent: typing.List[dict],
    match_attrs: typing.List[str],
    fields: typing.List[str],
) -> typing.List[dict]:
    """Copy `fields` from each child's linked parent onto the child.

    Links child→parent on `match_attrs`, then copies each requested parent
    field onto the child when the child does not already carry a non-null
    value for it. A no-op when `match_attrs` or `fields` is empty. The `_parent`
    annotation is not left on the returned records.
    """
    if not match_attrs or not fields:
        return list(child)

    linked = link(child, parent, match_attrs)
    out: typing.List[dict] = []
    for record in linked:
        matched = record.pop("_parent", None)
        if isinstance(matched, dict):
            for field in fields:
                if _is_empty(record.get(field)) and not _is_empty(matched.get(field)):
                    record[field] = matched.get(field)
        out.append(record)
    return out


# ── orchestrator ─────────────────────────────────────────────────────────────


# A YAML group can surface in the aggregated extract under a renamed key (e.g.
# `charges` -> `account_charges` from xray_to_extract). Resolve the metadata's
# group name to the actual key holding its records, mirroring score_extraction.py.
_GROUP_ALIASES = {
    "charges": ["charges", "account_charges"],
    "account_charges": ["account_charges", "charges"],
}


def _resolve_group_key(doc: dict, group_name: str) -> str:
    for cand in _GROUP_ALIASES.get(group_name, [group_name]):
        if isinstance(doc.get(cand), list):
            return cand
    return group_name


def apply_business_logic(doc: dict, group_metadata: dict) -> dict:
    """Apply per-group business-logic primitives to an aggregated extract dict.

    `group_metadata` maps a group name (a list-valued key in `doc`) to its
    optional `{unique_attrs, match_attrs, conflict_attrs, passthrough}` config.
    Returns a new dict; `doc` is not mutated. A no-op when `group_metadata` is
    empty/absent or carries no recognized keys.

    Order per group: surface intra-group conflicts (among records that dedup is
    about to collapse, so the disagreement is not silently lost) → dedup →
    passthrough (pulls linked parent fields in). Passthrough and any cross-group
    match read the (already-deduped) sibling groups in `doc`.
    """
    if not group_metadata:
        return dict(doc)

    result = dict(doc)

    # Conflicts-then-dedup, so downstream linking/passthrough see collapsed
    # groups that still carry any surfaced disagreement.
    for group_name, meta in group_metadata.items():
        if not isinstance(meta, dict):
            continue
        group_key = _resolve_group_key(result, group_name)
        records = result.get(group_key)
        if not isinstance(records, list):
            continue
        unique_attrs = meta.get("unique_attrs") or []
        conflict_attrs = meta.get("conflict_attrs") or []

        if conflict_attrs:
            # Surface conflicts among records sharing a dedup key (or across the
            # whole group when there is no dedup key) BEFORE dedup collapses them.
            records = _surface_conflicts_grouped(records, unique_attrs, conflict_attrs)
        if unique_attrs:
            records = dedup(records, unique_attrs)
        result[group_key] = records

    # Passthrough, reading the deduped sibling groups.
    for group_name, meta in group_metadata.items():
        if not isinstance(meta, dict):
            continue
        group_key = _resolve_group_key(result, group_name)
        records = result.get(group_key)
        if not isinstance(records, list):
            continue
        passthrough = meta.get("passthrough")
        if isinstance(passthrough, dict):
            parent_group = passthrough.get("from")
            fields = passthrough.get("fields") or []
            match_attrs = meta.get("match_attrs") or []
            parent_records = result.get(_resolve_group_key(result, parent_group))
            if isinstance(parent_records, list) and match_attrs and fields:
                result[group_key] = apply_passthrough(
                    records, parent_records, match_attrs, fields
                )

    return result


def _surface_conflicts_grouped(
    records: typing.List[dict],
    unique_attrs: typing.List[str],
    conflict_attrs: typing.List[str],
) -> typing.List[dict]:
    """Surface conflicts within each dedup-key group (whole group if no key).

    With a dedup key, records that will collapse together are checked against
    each other; without one, the whole group is treated as one set (the records
    are meant to describe the same entity).
    """
    if not unique_attrs:
        return surface_conflicts(records, conflict_attrs)

    buckets: typing.Dict[tuple, typing.List[dict]] = {}
    order: typing.List[tuple] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        key = _norm_key(record, unique_attrs)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(record)

    out: typing.List[dict] = []
    for key in order:
        out.extend(surface_conflicts(buckets[key], conflict_attrs))
    return out
