"""Pytest configuration and fixtures for s3-health tests."""

import os
import time
import pytest
import httpx


def is_service_available(url: str, timeout: float = 2) -> bool:
    """Check if an HTTP service is available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def pytest_configure(config):
    """Configure pytest and register custom markers."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring docker stack"
    )

    # Check if the FastAPI app is available
    app_available = is_service_available(
        "http://app_under_test:8000/health"
    ) or is_service_available("http://localhost:8000/health")

    # Store in config for later use
    config.app_available = app_available

    # Check if MinIO/S3 is available
    minio_endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    s3_available = is_service_available(f"{minio_endpoint}/minio/health/live", timeout=2)

    config.s3_available = s3_available


@pytest.fixture
def requires_docker_stack():
    """Fixture that skips test if Docker stack is not available."""
    app_available = is_service_available(
        "http://app_under_test:8000/health"
    ) or is_service_available("http://localhost:8000/health")

    minio_endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    s3_available = is_service_available(f"{minio_endpoint}/minio/health/live", timeout=2)

    if not (app_available and s3_available):
        pytest.skip("Docker stack (app + S3) is not available. Use 'docker-compose up' or './scripts/run_tests.sh'")

