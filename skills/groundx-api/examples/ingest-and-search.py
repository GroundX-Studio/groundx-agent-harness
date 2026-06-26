"""Ingest remote documents into GroundX, poll for completion, then search.

Required environment:
  GROUNDX_API_KEY  GroundX API key for the account that owns the bucket.

The example uses the direct REST API so it works in backends, scripts, and tests
without requiring an MCP client. It composes URLs from the `/api` host prefix plus
the documented `/v1/...` operation paths to avoid `/api/v1/v1/...` mistakes.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

GROUNDX_API_PREFIX = os.environ.get("GROUNDX_API_PREFIX", "https://api.groundx.ai/api")
API_KEY = os.environ["GROUNDX_API_KEY"]


def request_json(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{GROUNDX_API_PREFIX}{path}",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        },
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def ingest_remote(bucket_id: int, source_url: str, file_name: str, file_type: str) -> str:
    result = request_json(
        "POST",
        "/v1/ingest/documents/remote",
        json={
            "documents": [
                {
                    "bucketId": bucket_id,
                    "sourceUrl": source_url,
                    "fileName": file_name,
                    "fileType": file_type,
                    "processLevel": "full",
                }
            ]
        },
    )
    return result["ingest"]["processId"]


def wait_for_ingest(process_id: str, timeout_seconds: int = 600) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        result = request_json("GET", f"/v1/ingest/{process_id}")
        ingest = result["ingest"]
        status = ingest["status"]

        if status == "complete":
            return ingest
        if status in {"error", "cancelled"}:
            raise RuntimeError(f"GroundX ingest {process_id} ended with status {status}: {ingest}")

        time.sleep(5)

    raise TimeoutError(f"GroundX ingest {process_id} did not complete within {timeout_seconds}s")


def search_bucket(bucket_id: int, query: str) -> dict[str, Any]:
    return request_json(
        "POST",
        f"/v1/search/{bucket_id}?n=5&verbosity=2",
        json={"query": query, "relevance": 10},
    )["search"]


if __name__ == "__main__":
    bucket_id = int(os.environ["GROUNDX_BUCKET_ID"])
    process_id = ingest_remote(
        bucket_id=bucket_id,
        source_url=os.environ["GROUNDX_SOURCE_URL"],
        file_name=os.environ.get("GROUNDX_FILE_NAME", "source-document.pdf"),
        file_type=os.environ.get("GROUNDX_FILE_TYPE", "pdf"),
    )

    wait_for_ingest(process_id)
    search = search_bucket(bucket_id, os.environ.get("GROUNDX_QUERY", "summarize this document"))
    print(search["text"])
