"""Structured JSONL logger for extraction runs.

Each event lands on disk the moment it's emitted, so a sub-agent that
terminates mid-run does not lose inspection context. The resulting
`run.log` is a JSONL file — read with `jq`, `tail -f`, or any
line-oriented tool after the run.

Usage:
    from run_log import RunLog
    rl = RunLog("notes/extractx-runs/customer-001/v1/run.log")
    rl.event("workflow.create", workflow_id=wid)
    rl.event("ingest.poll", status="training", poll=3)
    rl.quota_snapshot(gx_client, label="after-v1")
    rl.close()

Or as a context manager:
    with RunLog("v1/run.log") as rl:
        rl.event("workflow.create", workflow_id=wid)
        ...

Event records have this shape (one JSON object per line):
    {"ts": "<ISO 8601 UTC>", "event": "<name>", ...kwargs}
"""

import datetime
import json
import os
import typing


class RunLog:
    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # buffering=1 forces line-buffered writes; each event is on disk
        # before the next call returns.
        self._file = open(path, "a", buffering=1)

    def event(self, name: str, /, **kwargs: typing.Any) -> None:
        # `name` is positional-only (PEP 570 `/`) so callers may safely
        # pass `name=<something>` as a data kwarg without colliding with
        # the event-name parameter.
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": name,
        }
        record.update(kwargs)
        self._file.write(json.dumps(record, default=str) + "\n")

    def quota_snapshot(self, gx_client: typing.Any, label: str = "") -> None:
        """Capture current quota via `gx.customer.get()` and log it.

        Records `file_tokens.value` and `searches.value` plus their max
        limits if available. Use this at run start and at the end of each
        iteration to track per-iteration consumption.
        """
        try:
            c = gx_client.customer.get()
            meters = getattr(c.customer.subscription, "meters", None)
        except Exception as exc:
            self.event("quota.snapshot.error", label=label, error=str(exc))
            return

        if meters is None:
            self.event("quota.snapshot.unavailable", label=label)
            return

        ft = getattr(meters, "file_tokens", None)
        sq = getattr(meters, "searches", None)
        self.event(
            "quota.snapshot",
            label=label,
            file_tokens_value=getattr(ft, "value", None) if ft else None,
            file_tokens_max=getattr(ft, "max_value", None) if ft else None,
            searches_value=getattr(sq, "value", None) if sq else None,
            searches_max=getattr(sq, "max_value", None) if sq else None,
        )

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> "RunLog":
        return self

    def __exit__(self, *args: typing.Any) -> None:
        self.close()
