"""Tests for safe extraction run logging."""

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_log import RunLog  # noqa: E402


def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_event_recursively_redacts_obvious_identity_and_secret_values(tmp_path):
    log_path = tmp_path / "run.log"
    with RunLog(str(log_path)) as rl:
        rl.event(
            "unsafe.payload",
            process_id="process-1",
            workflow_id="workflow-1",
            headers={
                "Authorization": "Bearer sk-test-secret-token",
                "X-API-Key": "groundx_test_secret_key",
            },
            contact="reviewer@example.com",
            nested=[
                {"private": "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"},
                "document-1",
            ],
        )

    [event] = read_events(log_path)
    payload = json.dumps(event)
    assert "process-1" in payload
    assert "workflow-1" in payload
    assert "document-1" in payload
    assert "reviewer@example.com" not in payload
    assert "sk-test-secret-token" not in payload
    assert "groundx_test_secret_key" not in payload
    assert "BEGIN PRIVATE KEY" not in payload
    assert payload.count("[REDACTED]") >= 4


def test_quota_snapshot_failure_is_sanitized_and_non_blocking(tmp_path):
    log_path = tmp_path / "run.log"

    class Customer:
        def get(self):
            raise ValueError(
                "validation failed for user owner@example.com with Authorization: "
                "Bearer sk-live-secret and X-API-Key: groundx_live_secret"
            )

    with RunLog(str(log_path)) as rl:
        rl.quota_snapshot(types.SimpleNamespace(customer=Customer()), label="run.start")

    [event] = read_events(log_path)
    payload = json.dumps(event)
    assert event["event"] == "quota.snapshot.unavailable"
    assert event["label"] == "run.start"
    assert event["blocking"] is False
    assert event["exception_type"] == "ValueError"
    assert event["reason"] == "sdk_response_validation_failed"
    assert "error" not in event
    assert "owner@example.com" not in payload
    assert "sk-live-secret" not in payload
    assert "groundx_live_secret" not in payload
