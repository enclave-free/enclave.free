#!/bin/sh
set -eu

requirements_dir="${1:-/app}"
python_bin="${PYTHON_BIN:-python}"

"$python_bin" -m pip install --no-cache-dir --no-deps \
    -r "$requirements_dir/requirements-cpu.txt"
"$python_bin" -m pip install --no-cache-dir \
    -r "$requirements_dir/requirements.txt"
