"""Tests using an in-process FastAPI TestClient against a real S3-compatible backend.

Two variants cover the same app logic:
- ``test_bucket_freshness_with_testcontainer_minio``: spins up its own MinIO via
  testcontainers. Intended for local ``pytest`` runs outside Docker. Skipped when
  ``RUNNING_IN_CONTAINER=true`` because testcontainers cannot resolve the
  host-mapped port of a nested container from inside the compose network.
- ``test_bucket_freshness_with_compose_minio``: uses the MinIO service that the
  Docker Compose test stack already provides. Skipped when that service is not
  reachable (i.e. outside the compose network).
"""

import os
import time
import boto3

import pytest
from fastapi.testclient import TestClient

from testcontainers.core.container import DockerContainer

from src.api import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUNNING_IN_CONTAINER = os.environ.get("RUNNING_IN_CONTAINER", "").lower() == "true"

# Compose-provided MinIO coordinates (set by docker-compose.test.yml)
_COMPOSE_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
_COMPOSE_KEY = os.environ.get("S3_KEY", "minioadmin")
_COMPOSE_SECRET = os.environ.get("S3_SECRET", "minioadmin")


def _s3_client(endpoint: str, key: str, secret: str) -> "boto3.client":
    """Return a boto3 S3 client pointed at *endpoint*."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="us-east-1",
    )


def _assert_freshness(client: TestClient, bucket: str) -> None:
    """Run the freshness assertions against *bucket* via *client*."""
    r = client.get(f"/buckets/{bucket}/freshness")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["newest_object"]["key"] == "fresh.txt"
    assert data["newest_object"]["age_seconds"] < 10


def wait_for_http(url: str, timeout: int = 10) -> bool:
    """Poll *url* until it returns HTTP 200 or *timeout* seconds elapse."""
    import requests

    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Service at {url} did not become ready in {timeout}s")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    _RUNNING_IN_CONTAINER,
    reason=(
        "testcontainers resolves MinIO via the Docker host-mapped port, which is "
        "unreachable from inside the compose network. Use "
        "test_bucket_freshness_with_compose_minio instead."
    ),
)
def test_bucket_freshness_with_testcontainer_minio() -> None:
    """Spin up a throw-away MinIO via testcontainers and exercise the freshness endpoint.

    Designed for local ``pytest`` runs where Docker is accessible from the host.
    """
    minio = (
        DockerContainer("minio/minio:latest")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_command("server /data")
        .with_exposed_ports(9000)
    )

    try:
        minio.start()
        host = minio.get_container_host_ip()
        port = minio.get_exposed_port(9000)
        endpoint = f"http://{host}:{port}"

        os.environ["S3_ENDPOINT"] = endpoint
        os.environ["S3_KEY"] = "minioadmin"
        os.environ["S3_SECRET"] = "minioadmin"

        s3 = _s3_client(endpoint, "minioadmin", "minioadmin")
        bucket = "tc-test-bucket"
        s3.create_bucket(Bucket=bucket)
        s3.put_object(Bucket=bucket, Key="fresh.txt", Body=b"hello testcontainers")

        _assert_freshness(TestClient(app), bucket)

    finally:
        try:
            minio.stop()
        except Exception:
            pass


@pytest.mark.skipif(
    not _RUNNING_IN_CONTAINER,
    reason="Requires the compose-provided MinIO service (RUNNING_IN_CONTAINER not set).",
)
def test_bucket_freshness_with_compose_minio() -> None:
    """Exercise the freshness endpoint against the compose-provided MinIO.

    Runs only inside the Docker Compose test stack where ``minio`` is reachable
    by its service hostname and the S3_* environment variables are already set.
    """
    os.environ["S3_ENDPOINT"] = _COMPOSE_ENDPOINT
    os.environ["S3_KEY"] = _COMPOSE_KEY
    os.environ["S3_SECRET"] = _COMPOSE_SECRET

    s3 = _s3_client(_COMPOSE_ENDPOINT, _COMPOSE_KEY, _COMPOSE_SECRET)
    bucket = "tc-test-bucket"

    # Ensure the bucket exists and is empty so we don't hit storage limits from
    # objects left behind by previous runs.
    try:
        s3.create_bucket(Bucket=bucket)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    # Delete all existing objects before writing the test object.
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            s3.delete_object(Bucket=bucket, Key=obj["Key"])

    s3.put_object(Bucket=bucket, Key="fresh.txt", Body=b"hello compose minio")

    _assert_freshness(TestClient(app), bucket)
