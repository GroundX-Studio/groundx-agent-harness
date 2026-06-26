"""Contract tests for live-run cleanup semantics."""

import os


def test_batch_runner_does_not_delete_buckets():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_extraction.py")
    with open(path, "r") as f:
        source = f.read()

    assert "gx.buckets.delete" not in source
    assert "cleanup.bucket.preserved" in source


def test_deploy_template_preserves_created_buckets_on_failure():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_workflow.py")
    with open(path, "r") as f:
        source = f.read()

    assert "gx.buckets.delete" not in source
    assert "bucketPreserved" in source
