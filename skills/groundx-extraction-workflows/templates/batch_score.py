#!/usr/bin/env python3
"""batch_score.py — OFFLINE batch scoring of a captured run. NO re-ingest, NO API.

The economical iteration loop: `batch_extraction.py` ingests once and writes a
run dir of captured artifacts (`<doc>.extracted.json` + `<doc>.xray.json`);
this scores that captured set against answer keys as many times as you like —
after tweaking an answer key, the comparison/aliasing logic, or just to score
the same run on another machine — without paying for ingest again.

    python batch_score.py <run_dir> --keys-dir answer_keys/ [--manifest m.csv] [--out run_dir]
    python batch_score.py <run_dir> --keys-dir answer_keys/ --artifact-kind final

By default, reads each raw `<doc>.extracted.json` in <run_dir> + its answer key.
Use `--artifact-kind final` only when you deliberately want to score
`<doc>.final_output.json`, the local diagnostic/business-logic output. It does
not silently score `<doc>.xray_diagnostic.json`.

Then writes:
    <out>/<doc>.accuracy.json        per-document field-level report
    <out>/aggregated.accuracy.json   consolidated report across the set

This is the offline sibling of `batch_extraction.py` (live) and the batch
sibling of `score_extraction.py` (single doc). It imports only the SDK-free
scoring engine in `score_extraction` — no GroundX dependency.
"""
import argparse
import glob
import json
import os
import sys
import typing

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import score_extraction as score  # noqa: E402


def aggregate_reports(
    per_doc: typing.List[dict],
    dimensions: typing.Optional[typing.Dict[str, typing.Dict[str, str]]] = None,
) -> dict:
    """Roll per-document score reports into a consolidated accuracy report.

    `per_doc` is a list of `{"doc": <name>, "report": <compare_extraction output>}`.
    `dimensions` optionally maps doc name → {dimension: value} (e.g. from a
    manifest) for per-dimension breakdowns (by vendor, by service_type, …).

    Returns per-field hit rates (singleton), field-level group accuracy, the top
    misses, per-dimension rollups, and overall structural-failure vs field-miss
    counts. Lives here (next to compare_extraction) so all scoring is one module;
    batch_extraction.py imports it.
    """
    field_hits: typing.Dict[str, typing.List[int]] = {}
    miss_counts: typing.Dict[str, int] = {}
    # group field-level accumulators: group -> field -> aggregated counts
    group_field: typing.Dict[str, typing.Dict[str, typing.Dict[str, int]]] = {}
    group_records: typing.Dict[str, typing.Dict[str, int]] = {}
    dim_acc: typing.Dict[str, typing.Dict[str, typing.List[int]]] = {}
    docs_with_structural_failure = 0
    doc_summaries = []

    for entry in per_doc:
        doc = entry["doc"]
        report = entry.get("report") or {}
        singleton = report.get("singleton") or []
        groups = report.get("groups") or {}

        doc_pass = doc_total = 0
        structural = False
        for r in singleton:
            field = r["field"]
            ok = 1 if r["status"] in ("PASS", "WARN (casing)", "WARN (value; key null)") else 0
            field_hits.setdefault(field, []).append(ok)
            if not ok:
                miss_counts[field] = miss_counts.get(field, 0) + 1
            doc_pass += ok
            doc_total += 1

        for gname, gres in groups.items():
            # gres is the compare_records dict: field_breakdown + record_summary.
            fb = (gres or {}).get("field_breakdown") or {}
            gf = group_field.setdefault(gname, {})
            for fname, counts in fb.items():
                acc = gf.setdefault(fname, {"pass": 0, "scored": 0, "not_found": 0, "field_mismatch": 0})
                acc["pass"] += counts.get("pass", 0)
                acc["scored"] += counts.get("scored", 0)
                acc["not_found"] += counts.get("not_found", 0)
                acc["field_mismatch"] += counts.get("field_mismatch", 0)
                doc_pass += counts.get("pass", 0)
                doc_total += counts.get("scored", 0)
            rs = (gres or {}).get("record_summary") or {}
            rc = group_records.setdefault(gname, {"matched": 0, "expected": 0, "extra": 0, "not_found": 0})
            for k in rc:
                rc[k] += rs.get(k, 0)
            if rs.get("not_found", 0):
                structural = True

        if structural:
            docs_with_structural_failure += 1

        # per-dimension rollup
        for dim, val in (dimensions or {}).get(doc, {}).items():
            bucket = dim_acc.setdefault(dim, {}).setdefault(val, [])
            bucket.append(doc_pass / doc_total if doc_total else 0.0)

        doc_summaries.append({
            "doc": doc,
            "pass": doc_pass,
            "total": doc_total,
            "accuracy": round(doc_pass / doc_total, 4) if doc_total else None,
        })

    def rate(lst: typing.List[int]) -> float:
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    def ratio(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    field_accuracy = {f: {"accuracy": rate(v), "n": len(v)} for f, v in sorted(field_hits.items())}

    # group_accuracy is FIELD-level (scored passes / scored fields), so a record
    # that misses one field no longer zeroes the whole group.
    group_accuracy: typing.Dict[str, dict] = {}
    group_field_accuracy: typing.Dict[str, dict] = {}
    group_misses: typing.Dict[str, int] = {}
    for gname, gf in sorted(group_field.items()):
        g_pass = sum(c["pass"] for c in gf.values())
        g_scored = sum(c["scored"] for c in gf.values())
        group_accuracy[gname] = {"accuracy": ratio(g_pass, g_scored), "n": g_scored}
        group_field_accuracy[gname] = {}
        for fname, c in sorted(gf.items()):
            if not c["scored"]:
                continue
            group_field_accuracy[gname][fname] = {
                "accuracy": ratio(c["pass"], c["scored"]),
                "n": c["scored"],
                "not_found": c["not_found"],
                "field_mismatch": c["field_mismatch"],
            }
            misses = c["not_found"] + c["field_mismatch"]
            if misses:
                group_misses[f"{gname}.{fname}"] = misses

    dim_rollup = {
        dim: {val: round(sum(rs) / len(rs), 4) for val, rs in vals.items()}
        for dim, vals in dim_acc.items()
    }
    all_oks = [ok for v in field_hits.values() for ok in v]
    all_group_pass = sum(c["pass"] for gf in group_field.values() for c in gf.values())
    all_group_scored = sum(c["scored"] for gf in group_field.values() for c in gf.values())
    overall = ratio(sum(all_oks) + all_group_pass, len(all_oks) + all_group_scored)
    top_misses = sorted(miss_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]
    group_top_misses = sorted(group_misses.items(), key=lambda kv: kv[1], reverse=True)[:15]

    return {
        "documents": len(per_doc),
        "overall_accuracy": overall,
        "docs_with_structural_failure": docs_with_structural_failure,
        "field_accuracy": field_accuracy,
        "group_accuracy": group_accuracy,
        "group_field_accuracy": group_field_accuracy,
        "group_record_coverage": {g: dict(c) for g, c in sorted(group_records.items())},
        "by_dimension": dim_rollup,
        "top_misses": [{"field": f, "miss_docs": c} for f, c in top_misses],
        "group_top_misses": [{"field": f, "misses": c} for f, c in group_top_misses],
        "per_document": doc_summaries,
    }



def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", help="dir of captured artifacts (a batch_extraction --out)")
    p.add_argument("--keys-dir", required=True, help="dir of answer keys (<doc>.json)")
    p.add_argument("--manifest", default=None, help="csv with filename + dimension columns")
    p.add_argument("--out", default=None, help="output dir for reports (default: run_dir)")
    p.add_argument(
        "--artifact-kind",
        choices=("raw", "final"),
        default="raw",
        help="raw scores <doc>.extracted.json; final scores <doc>.final_output.json",
    )
    args = p.parse_args()

    out_dir = args.out or args.run_dir
    os.makedirs(out_dir, exist_ok=True)
    manifest = score.load_manifest(args.manifest)
    suffix = ".extracted.json" if args.artifact_kind == "raw" else ".final_output.json"

    per_doc = []
    for ext_path in sorted(glob.glob(os.path.join(args.run_dir, f"*{suffix}"))):
        base = os.path.basename(ext_path)[: -len(suffix)]
        key_path = score.find_answer_key(args.keys_dir, base)
        if not key_path:
            print(f"skip {base}: no answer key", file=sys.stderr)
            continue
        with open(ext_path) as f:
            extracted = json.load(f)
        expected = score.load_answer_key(key_path)
        report = score.compare_extraction(extracted, expected)
        per_doc.append({"doc": base, "report": report})
        with open(os.path.join(out_dir, f"{base}.accuracy.json"), "w") as f:
            json.dump(aggregate_reports([{"doc": base, "report": report}]), f, indent=2, default=str)

    if not per_doc:
        print(f"no <doc>{suffix} with answer keys under {args.run_dir}", file=sys.stderr)
        return 2

    agg = aggregate_reports(per_doc, manifest)
    with open(os.path.join(out_dir, "aggregated.accuracy.json"), "w") as f:
        json.dump(agg, f, indent=2, default=str)

    print(f"{agg['documents']} docs | overall {agg['overall_accuracy']:.1%}")
    for g, v in agg["group_accuracy"].items():
        print(f"  {g}: {v['accuracy']:.1%} (n={v['n']} scored fields)")
    for d in agg["per_document"]:
        print(f"  {d['doc']}: {d['accuracy']:.1%}  ({d['pass']}/{d['total']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
