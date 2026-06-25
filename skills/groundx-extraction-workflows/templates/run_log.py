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
import re
import typing


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
KEY_SHAPED_RE = re.compile(r"\b(?:groundx|sk|gx)[-_][A-Za-z0-9._\-]{8,}\b")
# Keys are lowercased before lookup; keep canonical header spellings visible so
# scanner/tests cover common auth headers such as Authorization and X-API-Key.
SENSITIVE_KEYS = {
    "authorization",
    "x-api-key",
    "x_api_key",
    "api_key",
    "apikey",
    "bearer",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "private_key",
}


def _redact_string(value: str) -> str:
    value = PRIVATE_KEY_RE.sub("[REDACTED]", value)
    value = BEARER_RE.sub("Bearer [REDACTED]", value)
    value = KEY_SHAPED_RE.sub("[REDACTED]", value)
    value = EMAIL_RE.sub("[REDACTED]", value)
    return value


def _sanitize_for_log(value: typing.Any, key: typing.Optional[str] = None) -> typing.Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _sanitize_for_log(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_log(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_log(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _quota_failure_reason(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "validation" in text or "parse" in text or "model" in text:
        return "sdk_response_validation_failed"
    if "request" in text or "http" in text or "timeout" in text:
        return "request_failed"
    return "unavailable"


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
        record.update(_sanitize_for_log(kwargs))
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
            self.event(
                "quota.snapshot.unavailable",
                label=label,
                blocking=False,
                exception_type=type(exc).__name__,
                reason=_quota_failure_reason(exc),
            )
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
