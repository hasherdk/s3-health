#!/usr/bin/env bash
set -euo pipefail

# Run containerized tests via docker compose, aborting on container exit and using tests' exit code
COMPOSE_FILE="docker-compose.test.yml"

echo "Building and starting test compose stack (detached)..."
docker compose -f "${COMPOSE_FILE}" up --build -d

# Get the container id for the tests service
TEST_CONTAINER_ID=$(docker compose -f "${COMPOSE_FILE}" ps -q tests)
if [ -z "${TEST_CONTAINER_ID}" ]; then
	echo "Could not find tests container id"
	docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans || true
	exit 2
fi

echo "Waiting for tests container (${TEST_CONTAINER_ID}) to finish..."
# docker wait exits non-zero if the container itself exited non-zero, so capture
# the output (the exit code) separately from the shell exit status.
EXIT_CODE=$(docker wait "${TEST_CONTAINER_ID}") || true
# Fallback: if docker wait returned nothing (container already gone), inspect it.
if [ -z "${EXIT_CODE}" ]; then
	EXIT_CODE=$(docker inspect --format='{{.State.ExitCode}}' "${TEST_CONTAINER_ID}" 2>/dev/null || echo 2)
fi

echo "Tests finished with exit code: ${EXIT_CODE}"

echo "Fetching test logs..."
# Do NOT use --since: it is a relative timestamp and will miss logs from a
# container that has already exited by the time this line runs.
docker logs "${TEST_CONTAINER_ID}" || true

echo "Cleaning up..."
docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans || true

exit ${EXIT_CODE}
