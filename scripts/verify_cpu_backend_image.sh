#!/bin/sh
set -eu

image="${1:-enclavefree-core-backend:cpu}"
runtime="${CONTAINER_RUNTIME:-container}"

if ! command -v "$runtime" >/dev/null 2>&1; then
    echo "Container runtime not found: $runtime" >&2
    exit 1
fi

exec "$runtime" run --rm \
    --env SECRET_KEY=cpu-runtime-verification \
    --entrypoint python \
    "$image" \
    /usr/local/bin/verify_cpu_runtime.py
