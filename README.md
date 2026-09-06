# S3 Health

S3 Health is a lightweight application designed to monitor the health and availability of Amazon S3 or similar buckets, like MinIO. It can be used as a sidecar container alongside monitoring tools like Uptime Kuma to provide comprehensive visibility into your S3 infrastructure.

## Overview

This service performs health checks on configured S3 buckets by:
- Verifying bucket accessibility
- Checking the age of the newest object in the bucket
- Providing a simple REST API for health status

## Features

- Real-time S3 bucket health monitoring
- Customizable age thresholds for newest objects
- Simple HTTP API for integration with monitoring tools
- Low resource footprint suitable for sidecar deployment
- Compatible with S3-compatible storage services via custom endpoints

## Prerequisites

- Docker (for containerized deployment)
- S3 bucket access credentials
- Optional: Uptime Kuma or similar monitoring tool

## Quick Start

### Running with Docker

```bash
docker run -d \
  -e S3_KEY=your_access_key \
  -e S3_SECRET=your_secret_key \
  -e S3_ENDPOINT=https://s3.amazonaws.com \
  -p 8000:8000 \
  ghcr.io/hasherdk/s3-health:latest
```

### Running locally

```bash
git clone https://github.com/hasherdk/s3-health.git
cd s3-health
pip install -r requirements.txt
python src/main.py
```

## Configuration

Configure S3 Health using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_KEY` | AWS access key ID with S3 permissions | - |
| `S3_SECRET` | AWS secret access key | - |
| `S3_ENDPOINT` | S3 endpoint URL | https://s3.amazonaws.com |
| `S3_VERIFY_TLS` | Verify S3 TLS certificates; disable only for trusted test endpoints | `true` |

## API Usage

### Check Bucket Freshness

```
GET /buckets/{bucket_name}/freshness?max_age=24h
```

Parameters:
- `bucket_name`: Name of the S3 bucket to check
- `max_age`: (Optional) Maximum age of newest object (format: 24h, 30m, 1d). If not provided, only reports status without age validation.

Response:
- Status 200: Returns newest object details, only validates age when max_age is provided
- Status 500: Freshness check failed with detailed reason
- Status 422: Invalid `max_age` query format

Example successful response:
```json
{
  "status": "ok",
  "newest_object": {
    "key": "backups/2023-04-01.zip",
    "last_modified": "2023-04-01T12:00:00+00:00",
    "age_seconds": 3600
  }
}
```

### Check Bucket Storage Usage

```
GET /buckets/{bucket_name}/usage
```

Parameters:
- `bucket_name`: Name of the S3 bucket to check

Response:
- Status 200: Returns storage usage details
- Status 500: Check failed with detailed reason

Example successful response:
```json
{
  "status": "ok",
  "bucket": "my-data-bucket",
  "usage": {
    "object_count": 1205,
    "total_size_bytes": 2416542788,
    "total_size_formatted": "2.25 GB"
  }
}
```

## Integration with Uptime Kuma

[Uptime Kuma](https://github.com/louislam/uptime-kuma) is a popular open-source monitoring tool. Here's how to integrate S3 Health with it:

### Basic Integration - Freshness Check

1. Deploy S3 Health as a sidecar container alongside your Uptime Kuma instance
2. In Uptime Kuma, add a new monitor with the following settings:
   - **Monitor Type**: HTTP(s)
   - **URL**: `http://s3-health:8000/buckets/your-bucket-name/freshness?max_age=24h`
   - **Method**: GET
   - **Follow Redirects**: Yes
   - **Accept Status Codes**: 200
   - Set your desired notification settings

### Advanced Integration - Usage Thresholds

You can also monitor storage usage with JSON Query to verify:
- Object count is above/below a threshold
- Storage usage is within acceptable limits

#### Steps to Create a Usage Monitor:

1. In Uptime Kuma, add a new monitor with the following settings:
   - **Monitor Type**: HTTP(s) - Json Query
   - **URL**: `http://s3-health:8000/buckets/your-bucket-name/usage`
   - Set **JSON Query** to one of these examples:
     - Check object count: `usage.object_count > 10` (Ensures bucket has at least 10 objects)
     - Check storage size: `usage.total_size_bytes < 5368709120` (Ensures usage is below 5GB)
   - Set your desired notification settings

This allows you to monitor not just the presence of fresh objects, but also maintain awareness of storage growth and object counts, which can be useful for both backup verification and capacity planning.

### Docker Compose Example with Uptime Kuma

```yaml
version: '3'
services:
  uptime-kuma:
    image: louislam/uptime-kuma:latest
    ports:
      - "3001:3001"
    volumes:
      - uptime-kuma-data:/app/data
    restart: always

  s3-health:
    image: ghcr.io/hasherdk/s3-health:latest
    environment:
      - S3_KEY=your_access_key
      - S3_SECRET=your_secret_key
      - S3_ENDPOINT=https://s3.amazonaws.com
    restart: always

volumes:
  uptime-kuma-data:
```

## Tests and container publishing

Run the test suite without S3 credentials or a live bucket:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
docker build -t s3-health:ci .
bash tests/container-smoke.sh s3-health:ci
```

Every PR to `main`, including Dependabot and forks, runs pytest, builds native
AMD64 and ARM64 images, and checks `/health`, the Docker healthcheck, and non-root
execution. PR CI has read-only permissions and does not log into GHCR. GitHub
may require maintainer approval before running a first-time contributor's CI.

After CI succeeds, a separate `workflow_run` workflow copies the tested image
artifacts into **`ghcr.io/hasherdk/s3-health-pr`** and combines both architectures:

```bash
docker pull ghcr.io/hasherdk/s3-health-pr:pr-63
# Pin validation to a particular PR head commit using its full SHA:
docker pull ghcr.io/hasherdk/s3-health-pr:pr-63-sha-<full-head-sha>
```

Use that image in your existing Docker/Compose deployment for server validation.
These images contain unreviewed PR code. The publisher never checks out or runs
that code: it only copies image data, with destinations derived from GitHub API
metadata. Closed PRs and runs whose head is no longer current are skipped.
PR CI tests GitHub's merge ref (the proposed merge into `main`); the SHA in the
preview tag identifies the PR head, not the synthetic merge commit. Rerunning a
build can refresh the tag; use an image digest for an immutable deployment.

Preview images use a separate package so they cannot change the production
package's newest upload or its `latest` tag. The production workflow publishes
`ghcr.io/hasherdk/s3-health:latest` and `sha-<full-main-sha>` for `main` only,
after tests and both architecture smoke checks pass. Manual production runs
must also target `main`. The legacy `beta` tag is no longer updated; existing
registry tags are not deleted by these workflows.

### One-time setup and operational notes

- The PR publisher must first be merged into the default branch before GitHub
  will trigger it. This PR can validate CI, but cannot bootstrap its own publisher.
- After the first preview upload, set the `s3-health-pr` package visibility to
  public if anonymous server pulls are desired. Otherwise authenticate the
  server with a token that can read that package. Ensure this repository's
  Actions have write access to both packages if they already exist.
- Require the `test` and both `container` checks in branch protection to enforce
  the CI gate before merging. Workflow files alone do not enable branch protection.
- Image artifacts expire after three days. Rerun CI if a delayed publisher no
  longer has its artifacts. Registry previews and per-run architecture tags
  remain until removed; no automatic package deletion is enabled.
- GitHub controls the package page's suggested pull command. The documented
  production command is `docker pull ghcr.io/hasherdk/s3-health:latest`; a digest
  shown in GitHub's UI still refers to a specific image, independently of tags.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.
