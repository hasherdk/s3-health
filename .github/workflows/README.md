# CI/CD Workflow Documentation

## Overview

This repository uses a unified GitHub Actions workflow (`ci.yml`) to handle testing, building, and publishing Docker images for different scenarios.

## Workflow Triggers

### 1. Pull Request (PR)
**When:** A PR is opened or updated against the `main` branch.

**Behavior:**
- Runs the full test suite (`scripts/run_tests.sh`)
- Builds a Docker image for the PR
- Pushes the image with tag: `pr-{number}` (e.g., `pr-42`)
- **Does NOT** tag as `:latest`

**Example:**
```bash
# Pull the PR image for local testing
docker pull ghcr.io/YOUR_ORG/s3-health:pr-42
```

### 2. Push to Main (Merge)
**When:** A PR is merged or a commit is pushed directly to `main`.

**Behavior:**
- Runs the full test suite
- Builds a production Docker image
- Pushes with TWO tags:
  - `v1.0.{run_number}` (e.g., `v1.0.123`)
  - `latest`

**Example:**
```bash
# Pull the latest production image
docker pull ghcr.io/YOUR_ORG/s3-health:latest

# Or pull a specific version
docker pull ghcr.io/YOUR_ORG/s3-health:v1.0.123
```

### 3. Manual Workflow Dispatch
**When:** Manually triggered from the GitHub Actions UI.

**Behavior:**
- Allows testing from any branch
- Optional: Provide a custom tag (e.g., `v1.0.0-rc1`, `dev-feature-x`)
- If no custom tag is provided, uses: `{branch-name}-{short-sha}`
- **Does NOT** tag as `:latest`

**Example:**
```bash
# With custom tag (pre-release)
docker pull ghcr.io/YOUR_ORG/s3-health:v1.0.0-rc1

# Without custom tag (branch build)
docker pull ghcr.io/YOUR_ORG/s3-health:feature-auth-7a3b5c2
```

## How to Use

### Testing a PR Image Locally

1. Create a PR
2. Wait for the workflow to complete
3. Pull the image:
   ```bash
   docker pull ghcr.io/YOUR_ORG/s3-health:pr-{PR_NUMBER}
   docker run -p 8000:8000 \
     -e S3_ENDPOINT=your-endpoint \
     -e S3_KEY=your-key \
     -e S3_SECRET=your-secret \
     ghcr.io/YOUR_ORG/s3-health:pr-{PR_NUMBER}
   ```

### Creating a Pre-Release Image from a Branch

1. Go to **Actions** tab in GitHub
2. Select **CI/CD Pipeline** workflow
3. Click **Run workflow**
4. Choose your branch
5. (Optional) Enter a custom tag like `v1.0.0-rc1`
6. Click **Run workflow**

The image will be available shortly after the workflow completes.

### Deploying Production

Simply merge your PR to `main`. The workflow will automatically:
- Run all tests
- Build the image
- Tag as both `v1.0.{run_number}` and `latest`
- Push to the registry

## Versioning Strategy

### Automatic Versioning
- **Format:** `v1.0.{github.run_number}`
- **Example:** The 123rd workflow run produces `v1.0.123`
- **Benefits:**
  - Guaranteed unique version numbers
  - Monotonically increasing
  - No manual intervention required
  - No git commits needed

### Custom Versioning (Manual Dispatch Only)
You can override the automatic versioning by providing a custom tag when manually triggering the workflow.

**Recommended format:**
- Release candidates: `v1.0.0-rc1`, `v2.0.0-rc2`
- Feature branches: `feature-name-{short-description}`
- Hotfixes: `hotfix-{issue-number}`

## Testing the Workflow

### Local Testing (Before Push)
While you can't run GitHub Actions locally, you can:

1. **Test the Docker build:**
   ```bash
   docker build -t s3-health:test \
     --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
     --build-arg VCS_REF=$(git rev-parse HEAD) \
     --build-arg VERSION=test \
     .
   ```

2. **Run the test suite:**
   ```bash
   ./scripts/run_tests.sh
   ```

3. **Inspect image labels:**
   ```bash
   docker image inspect s3-health:test | jq '.[0].Config.Labels'
   ```

### First-Time Setup on GitHub

1. Push the workflow to your repository
2. Ensure GitHub Actions is enabled
3. Verify the `GITHUB_TOKEN` has write permissions to packages:
   - Go to **Settings → Actions → General**
   - Under **Workflow permissions**, ensure "Read and write permissions" is selected

## Image Registry

All images are pushed to **GitHub Container Registry (GHCR)**:
- Registry: `ghcr.io`
- Image path: `ghcr.io/{owner}/{repo}`
- Example: `ghcr.io/myorg/s3-health:latest`

### Making Images Public

By default, GHCR images are private. To make them public:
1. Go to your repository's **Packages** page
2. Click on the `s3-health` package
3. Click **Package settings**
4. Scroll to **Danger Zone**
5. Click **Change visibility** → **Public**

## Troubleshooting

### Workflow fails on test step
- Check the test logs in the GitHub Actions UI
- Run `./scripts/run_tests.sh` locally to reproduce
- Ensure Docker is available in the runner

### Image not found after workflow completes
- Verify the workflow completed successfully
- Check if you have permission to pull from GHCR
- Log in to GHCR: `echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin`

### Custom tag not applied
- Ensure you provided the tag in the "custom_tag" input field
- Tags must follow Docker naming conventions (lowercase, no spaces)

## Security Notes

- The workflow uses `GITHUB_TOKEN` for authentication (automatically provided)
- No secrets need to be manually configured
- Images run as non-root user (via distroless base image)
- Multi-platform builds (amd64 and arm64) are supported
