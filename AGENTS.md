# Agent Guidelines for S3 Health

This document provides comprehensive guidelines for AI agents and developers working on the `s3-health` repository. It outlines the build, test, and style standards required to maintain code quality and consistency.

## 1. Project Overview & Architecture

### Core Components
- **Application:** A lightweight FastAPI service for monitoring S3 bucket health.
- **Entry Point:** `src/main.py` launches the Uvicorn server.
- **API Logic:** `src/api.py` contains all route definitions and business logic.
- **Infrastructure:** Docker and Docker Compose are used for consistent deployment and testing.

### Design Philosophy
- **Stateless:** The application holds no state; it queries S3 on demand.
- **Configuration-driven:** All behavior is controlled via environment variables.
- **Resilient:** It must handle S3 outages gracefully without crashing.

## 2. Development Environment

### Prerequisites
- **Python:** 3.11 or higher.
- **Docker:** Required for running the full test suite and building the production image.
- **Docker Compose:** Required for integration tests.

### Setup
To set up a local development environment (without Docker):
```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install production and test dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt
```

## 3. Build, Lint, and Test Commands

### Running Tests
Testing is the most critical part of the workflow. The project supports two modes:

#### A. Full Containerized Suite (Recommended for CI/Final Check)
This script builds the Docker image, spins up a MinIO container (S3 mock), runs the tests inside a test container, and tears everything down.
```bash
./scripts/run_tests.sh
```
*Note: Ensure Docker is running. This process mimics the CI environment exactly.*

#### B. Local Development Tests (Fast Feedback)
For rapid iteration, you can run tests locally using `pytest`. The project uses `testcontainers` to spin up ephemeral MinIO instances for integration tests without needing the full stack.

**Run all tests:**
```bash
pytest
```

**Run a specific test file:**
```bash
pytest src/tests/test_s3_health_tc.py
```
*Note: Prefer `test_s3_health_tc.py` for local dev as it manages its own MinIO container. `test_s3_health.py` expects an external stack.*

**Run a specific test case:**
```bash
pytest src/tests/test_s3_health_tc.py::test_bucket_freshness_with_testcontainer_minio
```

### Linting & Formatting
While there is no strict CI enforcement yet, agents **must** adhere to these standards:

- **Formatter:** Code should be formatted compatible with `Black`.
- **Import Sorting:** Imports should be sorted compatible with `isort`.
- **Line Length:** 88 characters is the soft limit; 100 is the hard limit.
- **Docstrings:** All public modules, classes, and functions must have docstrings.

To verify style manually:
```bash
# Check for obvious syntax or style issues (if tools are installed)
# pip install ruff black
ruff check .
black --check .
```

## 4. Code Style & Conventions

### Python Guidelines
- **Type Hints:** strictly required for all function arguments and return values.
  ```python
  # Good
  def calculate_age(last_modified: datetime) -> int:
      ...
  
  # Bad
  def calculate_age(last_modified):
      ...
  ```
- **Naming:**
    - Variables/Functions: `snake_case`
    - Classes: `PascalCase`
    - Constants: `UPPER_CASE`
- **Imports:**
    - Group 1: Standard library (e.g., `os`, `datetime`)
    - Group 2: Third-party libraries (e.g., `fastapi`, `boto3`)
    - Group 3: Local imports (e.g., `from src.api import app`)
    - Use absolute imports for local modules to avoid confusion.

### FastAPI & API Design
- **Route Handlers:** Must be `async def` to ensure non-blocking I/O.
- **Response Models:** While simple dicts are currently used, prefer Pydantic models for complex responses in future work.
- **Documentation:**
    - Use Markdown in docstrings.
    - Annotate `Path` and `Query` parameters with `description` and `example`.
    - Use `tags` to categorize endpoints in Swagger UI.

### Error Handling Pattern
Always handle exceptions gracefully and return meaningful HTTP errors.
1. Catch specific exceptions (e.g., `ClientError` from boto3).
2. Raise `HTTPException` with the appropriate status code (400, 404, 500).
3. Provide a structured `detail` dictionary, not just a string.

```python
try:
    s3.head_object(Bucket=bucket, Key=key)
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == "404":
        raise HTTPException(
            status_code=404,
            detail={"status": "error", "message": f"Object {key} not found"}
        )
    raise HTTPException(
        status_code=500,
        detail={"status": "error", "message": str(e)}
    )
```

### AWS / S3 Interaction
- **Library:** Use `boto3` for all S3 interactions.
- **Client Creation:** Instantiate clients inside functions or as dependencies, not at module level, to allow for easier mocking and configuration updates.
- **Configuration:** Never hardcode region or credentials.
    - Use `os.environ.get("S3_ENDPOINT")`
    - Use `os.environ.get("S3_KEY")`
    - Use `os.environ.get("S3_SECRET")`

## 5. Workflow Rules

### Creating New Features
1. **Plan:** Understand the requirement and identify necessary S3 permissions.
2. **Test First:** Write a test case in `src/tests/test_s3_health_tc.py` that fails.
3. **Implement:** Write the code in `src/api.py`.
4. **Verify:** Run the test to ensure it passes.
5. **Document:** specific parameters in the docstring.

### Docker Considerations
If you add a new Python dependency:
1. Add it to `requirements.txt`.
2. Rebuild the test image: `docker compose -f docker-compose.test.yml build`.
3. Run the full test suite to ensure no regressions.

### Commit Messages
- Use the imperative mood ("Add feature" not "Added feature").
- Reference issue numbers if applicable.
- Keep the first line under 50 characters.

## 6. Common Troubleshooting

- **Port Conflicts:** If port 8000 is in use, modify `docker-compose.yml` or run locally on a different port:
  ```bash
  uvicorn src.api:app --port 8001
  ```
- **MinIO Connection:** If tests fail with connection refused, ensure the `S3_ENDPOINT` is correctly set. Inside Docker it's usually `http://minio:9000`, but locally it might be `http://localhost:9000`. `testcontainers` handles this automatically in `test_s3_health_tc.py`.
