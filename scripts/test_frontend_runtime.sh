#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime="${FRONTEND_CONTAINER_RUNTIME:-${1:-auto}}"
host_port="${FRONTEND_TEST_PORT:-55173}"
image="enclave-frontend-ticket-507:local"
container_name="enclave-frontend-ticket-507"

if [[ "$runtime" == "auto" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]] && command -v container >/dev/null 2>&1; then
    runtime="apple"
  else
    runtime="docker"
  fi
fi

case "$runtime" in
  apple)
    cleanup_container() {
      container delete --force "$container_name" >/dev/null 2>&1 || true
    }
    build_image() {
      container build --tag "$image" "$repo_root/frontend"
    }
    start_container() {
      container run --detach --name "$container_name" \
        --publish "127.0.0.1:${host_port}:80" "$image" >/dev/null
    }
    verify_container_health() {
      container exec "$container_name" \
        wget --no-verbose --tries=1 --spider http://127.0.0.1/
      container inspect "$container_name" | python3 -c '
import json
import sys

inspection = json.load(sys.stdin)
if inspection[0]["status"]["state"] != "running":
    raise SystemExit("Apple container is not running")
'
    }
    ;;
  docker)
    cleanup_container() {
      docker rm --force "$container_name" >/dev/null 2>&1 || true
    }
    build_image() {
      docker build --tag "$image" "$repo_root/frontend"
    }
    start_container() {
      docker run --detach --name "$container_name" \
        --publish "127.0.0.1:${host_port}:80" "$image" >/dev/null
    }
    verify_container_health() {
      docker exec "$container_name" \
        wget --no-verbose --tries=1 --spider http://127.0.0.1/
      for _ in {1..60}; do
        health_status="$(docker inspect --format '{{.State.Health.Status}}' "$container_name")"
        if [[ "$health_status" == "healthy" ]]; then
          return
        fi
        if [[ "$health_status" == "unhealthy" ]]; then
          echo "Frontend container reported unhealthy" >&2
          docker inspect --format '{{json .State.Health}}' "$container_name" >&2
          exit 1
        fi
        sleep 1
      done
      echo "Frontend container did not report healthy within 60 seconds" >&2
      exit 1
    }
    ;;
  *)
    echo "Unsupported frontend container runtime: $runtime (expected auto, apple, or docker)" >&2
    exit 2
    ;;
esac

trap cleanup_container EXIT
cleanup_container
build_image
start_container

for _ in {1..60}; do
  if curl --fail --silent --show-error "http://127.0.0.1:${host_port}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl --fail --silent --show-error "http://127.0.0.1:${host_port}/" >/dev/null
FRONTEND_RUNTIME_URL="http://127.0.0.1:${host_port}" \
  python3 "$repo_root/scripts/tests/DEPLOYMENT/test_frontend_http.py"
verify_container_health
