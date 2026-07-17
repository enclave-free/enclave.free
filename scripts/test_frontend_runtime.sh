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

cleanup() {
  if [[ "$runtime" == "apple" ]]; then
    container delete --force "$container_name" >/dev/null 2>&1 || true
  else
    docker rm --force "$container_name" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
cleanup

case "$runtime" in
  apple)
    container build --tag "$image" "$repo_root/frontend"
    container run --detach --name "$container_name" \
      --publish "127.0.0.1:${host_port}:80" "$image" >/dev/null
    ;;
  docker)
    docker build --tag "$image" "$repo_root/frontend"
    docker run --detach --name "$container_name" \
      --publish "127.0.0.1:${host_port}:80" "$image" >/dev/null
    ;;
  *)
    echo "Unsupported frontend container runtime: $runtime (expected auto, apple, or docker)" >&2
    exit 2
    ;;
esac

for _ in {1..60}; do
  if curl --fail --silent --show-error "http://127.0.0.1:${host_port}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl --fail --silent --show-error "http://127.0.0.1:${host_port}/" >/dev/null
FRONTEND_RUNTIME_URL="http://127.0.0.1:${host_port}" \
  python3 "$repo_root/scripts/tests/DEPLOYMENT/test_frontend_http.py"
