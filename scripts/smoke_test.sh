#!/usr/bin/env bash
# Smoke-test the supported Compose topology through its public and provider seams.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE=(docker compose -f docker-compose.infra.yml -f docker-compose.app.yml)
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://localhost:18000}"

curl -fsS "$GATEWAY_BASE_URL/test"
printf '\n'
curl -fsS "$GATEWAY_BASE_URL/health"
printf '\n'
curl -fsS "$GATEWAY_BASE_URL/llm/test"
printf '\n'

# Run from the core-backend container so the check reaches the proxy on the
# private Compose network and uses the same Model Provider configuration.
"${COMPOSE[@]}" exec -T core-backend \
  python - < "$SCRIPT_DIR/tinfoil_response_integrity_smoke.py"
