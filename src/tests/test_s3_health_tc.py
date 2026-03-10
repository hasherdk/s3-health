import os
import time
import boto3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from testcontainers.core.container import DockerContainer

from src.api import app


def wait_for_http(url, timeout=10):
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


@pytest.mark.integration
def test_bucket_freshness_with_testcontainer_minio():
    # Start MinIO via testcontainers
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

        # make app point to this MinIO
        os.environ["S3_ENDPOINT"] = endpoint
        os.environ["S3_KEY"] = "minioadmin"
        os.environ["S3_SECRET"] = "minioadmin"

        # Create bucket and object using boto3 pointing to MinIO
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="us-east-1",
        )
        bucket = "tc-test-bucket"
        s3.create_bucket(Bucket=bucket)
        s3.put_object(Bucket=bucket, Key="fresh.txt", Body=b"hello testcontainers")

        # Use FastAPI TestClient to call the app in-process
        client = TestClient(app)

        r = client.get(f"/buckets/{bucket}/freshness")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["newest_object"]["key"] == "fresh.txt"
        assert data["newest_object"]["age_seconds"] < 10

    finally:
        try:
            minio.stop()
        except Exception:
            pass
