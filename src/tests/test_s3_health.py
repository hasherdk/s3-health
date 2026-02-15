import os
import time
from datetime import datetime, timezone, timedelta

import boto3
import httpx

MINIO_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
ACCESS_KEY = os.environ.get("S3_KEY", "minioadmin")
SECRET_KEY = os.environ.get("S3_SECRET", "minioadmin")

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )

def wait_for_http(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Service at {url} did not become ready in {timeout}s")


def test_health_endpoint_is_up():
    assert wait_for_http("http://app_under_test:8000/health") or wait_for_http("http://localhost:8000/health")


def test_bucket_freshness_and_usage(tmp_path):
    s3 = s3_client()
    bucket = "test-bucket"

    # Create bucket
    s3.create_bucket(Bucket=bucket)

    # Put an object with current timestamp
    now = datetime.now(timezone.utc)
    s3.put_object(Bucket=bucket, Key="fresh.txt", Body=b"fresh content")

    # Determine base URL for the app (prefer compose network hostname)
    base_url = None
    try:
        if wait_for_http("http://app_under_test:8000/health", timeout=5):
            base_url = "http://app_under_test:8000"
    except Exception:
        pass
    if not base_url:
        # fallback to localhost for runs outside compose network
        if wait_for_http("http://localhost:8000/health", timeout=5):
            base_url = "http://localhost:8000"
    if not base_url:
        raise RuntimeError("Could not determine application base URL")

    # Call freshness endpoint without max_age
    r = httpx.get(f"{base_url}/buckets/{bucket}/freshness", timeout=5.0)

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["newest_object"]["key"] == "fresh.txt"

    # Call freshness with a very small max_age to force failure.
    # FastAPI param validation returns 422 Unprocessable Entity for invalid query formats.
    r2 = httpx.get(f"{base_url}/buckets/{bucket}/freshness?max_age=1s", timeout=5.0)
    assert r2.status_code == 422

    # Usage endpoint
    r3 = httpx.get(f"{base_url}/buckets/{bucket}/usage", timeout=5.0)
    assert r3.status_code == 200
    usage = r3.json()
    assert usage["status"] == "ok"
    assert usage["usage"]["object_count"] >= 1
