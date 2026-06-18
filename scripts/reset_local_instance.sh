#!/usr/bin/env bash
#
# Reset the local Enclave Compose instance for smoke testing.
#
# Default behavior:
#   - stop the stack
#   - remove runtime state volumes
#   - preserve embedding cache
#   - rebuild/start the stack
#   - run gateway smoke checks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILES=(-f docker-compose.infra.yml -f docker-compose.app.yml)
COMPOSE=(docker compose "${COMPOSE_FILES[@]}")
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')}"

RESET_ALL=false
BUILD=true
SMOKE=true
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: scripts/reset_local_instance.sh [options]

Options:
  --all          Also remove the embedding model cache volume.
  --no-build     Start existing images with `up -d` instead of `up --build -d`.
  --skip-smoke   Do not run gateway smoke checks after startup.
  --dry-run      Print commands without changing Docker state.
  -h, --help     Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      RESET_ALL=true
      ;;
    --no-build)
      BUILD=false
      ;;
    --skip-smoke)
      SMOKE=false
      ;;
    --dry-run)
      DRY_RUN=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

print_command() {
  printf '%q' "$1"
  shift
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
}

run() {
  print_command "$@"
  if [[ "$DRY_RUN" == false ]]; then
    "$@"
  fi
}

volume_name() {
  local volume="$1"
  printf '%s_%s' "$PROJECT_NAME" "$volume"
}

configured_volumes() {
  "${COMPOSE[@]}" config --volumes
}

should_reset_volume() {
  local volume="$1"
  case "$volume" in
    qdrant_data|sage_postgres_data|sage_workspace|sqlite_data)
      return 0
      ;;
    embedding_cache)
      [[ "$RESET_ALL" == true ]]
      return
      ;;
    *)
      return 1
      ;;
  esac
}

remove_volume() {
  local full_name="$1"

  if [[ "$DRY_RUN" == true ]]; then
    run docker volume rm "$full_name"
    return
  fi

  if docker volume inspect "$full_name" >/dev/null 2>&1; then
    run docker volume rm "$full_name"
  else
    echo "Skipping missing volume: $full_name"
  fi
}

compose_volumes=()
while IFS= read -r volume; do
  [[ -n "$volume" ]] && compose_volumes+=("$volume")
done < <(configured_volumes)

fallback_volumes=(
  qdrant_data
  sage_postgres_data
  sage_workspace
  sqlite_data
)

if [[ "$RESET_ALL" == true ]]; then
  fallback_volumes+=(embedding_cache)
fi

if [[ ${#compose_volumes[@]} -eq 0 ]]; then
  compose_volumes=("${fallback_volumes[@]}")
fi

run "${COMPOSE[@]}" down

for volume in "${compose_volumes[@]}"; do
  if should_reset_volume "$volume"; then
    remove_volume "$(volume_name "$volume")"
  fi
done

if [[ "$BUILD" == true ]]; then
  run "${COMPOSE[@]}" up --build -d
else
  run "${COMPOSE[@]}" up -d
fi

if [[ "$SMOKE" == true ]]; then
  run lsof -nP -iTCP:18000 -sTCP:LISTEN
  run curl -fsS http://localhost:18000/test
  run curl -fsS http://localhost:18000/llm/test
fi
