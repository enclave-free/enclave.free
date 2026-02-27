#!/usr/bin/env sh

set -eu

DEFAULT_SQLITE_PATH="/data/enclavefree.db"
LEGACY_SQLITE_PATH="/data/sanctum.db"
SQLITE_PATH_RESOLVED="${SQLITE_PATH:-$DEFAULT_SQLITE_PATH}"
SQLITE_MIGRATE_LEGACY_DB="${SQLITE_MIGRATE_LEGACY_DB:-true}"

copy_sqlite_with_sidecars() {
  src="$1"
  dst="$2"
  cp "$src" "$dst"
  for suffix in -wal -shm; do
    if [ -f "${src}${suffix}" ]; then
      cp "${src}${suffix}" "${dst}${suffix}"
    fi
  done
}

migrate_legacy_sqlite() {
  src="$1"
  dst="$2"
  tmp="${dst}.migrating.$$"

  if command -v sqlite3 >/dev/null 2>&1; then
    echo "[startup] Migrating legacy SQLite via sqlite3 backup API (WAL-safe)."
    rm -f "$tmp"
    if sqlite3 "$src" ".timeout 5000" ".backup '$tmp'"; then
      mv "$tmp" "$dst"
      return 0
    fi

    echo "[startup] WARNING: sqlite3 backup migration failed; falling back to file copy with WAL sidecars."
    rm -f "$tmp"
  else
    echo "[startup] WARNING: sqlite3 not found; falling back to file copy with WAL sidecars."
  fi

  copy_sqlite_with_sidecars "$src" "$dst"
}

if [ "$SQLITE_PATH_RESOLVED" = "$DEFAULT_SQLITE_PATH" ] && [ -f "$LEGACY_SQLITE_PATH" ] && [ ! -f "$DEFAULT_SQLITE_PATH" ]; then
  case "$SQLITE_MIGRATE_LEGACY_DB" in
    1|true|TRUE|yes|YES|on|ON)
      echo "[startup] Detected legacy SQLite file at '$LEGACY_SQLITE_PATH'."
      echo "[startup] Migrating to '$DEFAULT_SQLITE_PATH' before backend startup."
      migrate_legacy_sqlite "$LEGACY_SQLITE_PATH" "$DEFAULT_SQLITE_PATH"
      ;;
    *)
      echo "[startup] ERROR: Found legacy SQLite file '$LEGACY_SQLITE_PATH' but '$DEFAULT_SQLITE_PATH' is missing."
      echo "[startup] Run one-time migration (WAL-safe): sqlite3 '$LEGACY_SQLITE_PATH' \".backup '$DEFAULT_SQLITE_PATH'\""
      echo "[startup] Or set SQLITE_MIGRATE_LEGACY_DB=true to allow automatic migration at startup."
      exit 1
      ;;
  esac
fi

if [ "$SQLITE_PATH_RESOLVED" = "$DEFAULT_SQLITE_PATH" ] && [ -f "$LEGACY_SQLITE_PATH" ] && [ -f "$DEFAULT_SQLITE_PATH" ]; then
  echo "[startup] Legacy and current SQLite files both exist. Using '$SQLITE_PATH_RESOLVED'."
fi

python seed.py

# UVICORN_RELOAD: set to 1/true/yes/on to enable file-watching (dev). Default: false.
set -- uvicorn main:app --host 0.0.0.0 --port 8000
case "${UVICORN_RELOAD:-false}" in
  1|true|TRUE|yes|YES|on|ON) set -- "$@" --reload ;;
esac
exec "$@"
