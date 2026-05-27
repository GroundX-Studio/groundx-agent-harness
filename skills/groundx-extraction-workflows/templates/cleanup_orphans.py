#!/usr/bin/env python3
"""Janitor script for orphan GroundX workflows.

A workflow is considered an orphan when `relationships.ids` is empty
or null — it was created but never attached to a bucket. Orphans can
accumulate when a run crashes mid-setup (before `workflows.add_to_id`
completes), or when a workflow is manually detached.

This script lists orphan workflows and deletes them on `--yes`. By
default it runs in dry-run mode and only prints what it would do.

Usage:
    python cleanup_orphans.py                # dry-run: list orphans only
    python cleanup_orphans.py --yes          # delete all listed orphans
    python cleanup_orphans.py --name-prefix extractx-  # only those matching prefix

Reads `.env` for `GROUNDX_API_KEY`.

Safety:
    - Default is dry-run. `--yes` is required to actually delete.
    - Workflows attached to any bucket are never touched.
    - Each delete is logged to stdout; failures don't stop the run.
"""

import argparse
import os
import sys
import typing

import dotenv

# Resolve .env from the user's cwd, not the script's __file__ tree.
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from groundx import GroundX


def find_orphans(gx: GroundX, name_prefix: typing.Optional[str] = None) -> typing.List[typing.Any]:
    res = gx.workflows.list()
    orphans = []
    for wf in res.workflows or []:
        rels = wf.relationships.ids if wf.relationships else None
        if rels:
            continue
        if name_prefix and not (wf.name or "").startswith(name_prefix):
            continue
        orphans.append(wf)
    return orphans


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete the orphans. Without this flag the script only lists them.",
    )
    parser.add_argument(
        "--name-prefix",
        default=None,
        help="Only consider workflows whose name starts with this prefix.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GROUNDX_API_KEY")
    if not api_key:
        print("ERROR: GROUNDX_API_KEY is not set", file=sys.stderr)
        return 2

    gx = GroundX(
        api_key=api_key,
        base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
    )

    orphans = find_orphans(gx, name_prefix=args.name_prefix)
    if not orphans:
        print("no orphan workflows found")
        return 0

    print(f"found {len(orphans)} orphan workflow(s):")
    for wf in orphans:
        print(f"  {wf.workflow_id}  [{wf.name or '(unnamed)'}]")

    if not args.yes:
        print("\ndry-run only. re-run with --yes to delete.")
        return 0

    print("\ndeleting...")
    deleted = 0
    errors = 0
    for wf in orphans:
        try:
            gx.workflows.delete(id=wf.workflow_id)
            print(f"  deleted {wf.workflow_id}")
            deleted += 1
        except Exception as e:
            print(f"  ERROR deleting {wf.workflow_id}: {e}", file=sys.stderr)
            errors += 1

    print(f"\ndone. deleted={deleted} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
