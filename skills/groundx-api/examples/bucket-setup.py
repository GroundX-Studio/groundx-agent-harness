"""Create a bucket, create a group, and attach the bucket to the group.

Required environment:
  GROUNDX_API_KEY  GroundX API key for the account that owns the resources.

This direct REST example uses the documented `/v1/...` operation paths with the
`https://api.groundx.ai/api` host prefix. If your HTTP client base URL is already
`https://api.groundx.ai/api/v1`, remove the leading `/v1` from each path.
"""

from __future__ import annotations

import os
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


def create_bucket(name: str) -> int:
    result = request_json("POST", "/v1/bucket", json={"name": name})
    return result["bucket"]["bucketId"]


def create_group(name: str) -> int:
    result = request_json("POST", "/v1/group", json={"name": name})
    return result["group"]["groupId"]


def add_bucket_to_group(group_id: int, bucket_id: int) -> None:
    request_json("POST", f"/v1/group/{group_id}/bucket/{bucket_id}")


if __name__ == "__main__":
    bucket_id = create_bucket(os.environ.get("GROUNDX_BUCKET_NAME", "project-documents"))
    group_id = create_group(os.environ.get("GROUNDX_GROUP_NAME", "project-group"))
    add_bucket_to_group(group_id, bucket_id)
    print({"bucketId": bucket_id, "groupId": group_id})
