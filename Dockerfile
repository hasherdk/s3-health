# Multi-stage build: builder creates a virtualenv and installs dependencies,
# final stage uses a distroless python runtime (nonroot) for minimal attack surface.

# Build arguments for metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

FROM python:3.14-slim AS builder

# Set working dir
WORKDIR /src

# Install python dependencies into a target directory (avoids venv shebang issues).
# Build wheels so transitive dependencies are included and compiled if needed.
COPY requirements.txt /src/
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc python3-dev libffi-dev libpq-dev \
  && python -m pip install --upgrade pip setuptools wheel \
  && python -m pip wheel -r /src/requirements.txt -w /wheels \
  && python -m pip install --no-cache-dir /wheels/* --target /app/.packages \
  && rm -rf /wheels /var/lib/apt/lists/*

# Copy application sources
COPY src /src

# Make files world-readable/executable so the non-root user in the final image
# can access and execute them.
RUN chmod -R a+rX /app/.packages /src


FROM gcr.io/distroless/python3:nonroot

# OCI metadata labels
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="s3-health" \
      org.opencontainers.image.description="Lightweight FastAPI service for monitoring S3 bucket health" \
      org.opencontainers.image.licenses="GPL-3.0"

# Copy installed packages and application from the builder
COPY --from=builder /app/.packages /app/.packages
COPY --from=builder /src /app

# Add packages to PYTHONPATH so distroless python can import them
ENV PYTHONPATH=/app/.packages
WORKDIR /app

EXPOSE 8000

# Simple HTTP healthcheck that expects a 200 from /health
# Pass '-c' directly — the distroless python ENTRYPOINT will be prepended.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python","-c","import urllib.request,sys; resp=urllib.request.urlopen('http://127.0.0.1:8000/health'); sys.exit(0 if resp.getcode()==200 else 1)"]

# Run the application — the distroless image provides python as the ENTRYPOINT,
# so supplying the script path as CMD makes the runtime execute `python main.py`.
CMD ["main.py"]
