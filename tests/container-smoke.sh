#!/usr/bin/env bash
set -euo pipefail
image=${1:-s3-health:ci}
container=$(docker run -d --health-interval=1s --health-start-period=1s "$image")
cleanup() {
  docker logs "$container"
  docker rm -f "$container" >/dev/null
}
trap cleanup EXIT
for attempt in {1..60}; do
  status=$(docker inspect --format '{{.State.Health.Status}}' "$container")
  if [ "$status" = healthy ]; then
    docker exec "$container" python -c 'import os; assert os.getuid() != 0'
    docker exec "$container" python -c 'import json, urllib.request; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/health")) == {"status": "ok"}'
    exit 0
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$container")" != true ]; then
    break
  fi
  sleep 1
done
echo 'Container did not become healthy' >&2
exit 1
