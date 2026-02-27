#!/usr/bin/env bash
#
# EnclaveFree Backup Script
# Creates backups of Neo4j and Qdrant data stores
#
# Usage: ./scripts/backup.sh [backup_dir]
#
# Default backup location: ./backups/<timestamp>/
#

set -euo pipefail

# Configuration
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_COLLECTION_OVERRIDE_SET="${QDRANT_COLLECTION+x}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-enclavefree_knowledge}"
QDRANT_LEGACY_COLLECTION="${QDRANT_LEGACY_COLLECTION:-sanctum_knowledge}"
NEO4J_VOLUME="${NEO4J_VOLUME:-hrf-26-hackathon_neo4j_data}"
QDRANT_VOLUME="${QDRANT_VOLUME:-hrf-26-hackathon_qdrant_data}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_BASE="${1:-./backups}"
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"
log_info "Backup directory: $BACKUP_DIR"

# -----------------------------------------------------------------------------
# 1. Qdrant Snapshot (via REST API)
# -----------------------------------------------------------------------------
log_info "Creating Qdrant snapshot..."

QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

# Check if Qdrant is reachable
if ! curl -s "${QDRANT_URL}/collections" > /dev/null 2>&1; then
    log_warn "Qdrant not reachable at ${QDRANT_URL} - skipping API snapshot"
else
    backup_qdrant_collection() {
        local collection="$1"
        local exists
        exists=$(curl -s "${QDRANT_URL}/collections/${collection}" | grep -c '"status":"ok"' || true)

        if [ "$exists" -eq 0 ]; then
            log_warn "Collection '${collection}' not found - skipping Qdrant API snapshot"
            return
        fi

        local snapshot_response snapshot_name
        snapshot_response=$(curl -s -X POST "${QDRANT_URL}/collections/${collection}/snapshots")
        snapshot_name=$(echo "$snapshot_response" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || true)

        if [ -z "$snapshot_name" ]; then
            log_warn "Failed to create Qdrant snapshot via API for '${collection}'"
            return
        fi

        local snapshot_file="${BACKUP_DIR}/qdrant_${collection}.snapshot"
        log_info "Snapshot created for '${collection}': $snapshot_name"
        if ! curl -fsS -o "$snapshot_file" \
            "${QDRANT_URL}/collections/${collection}/snapshots/${snapshot_name}"; then
            log_error "Failed to download Qdrant snapshot for '${collection}'"
            exit 1
        fi
        if [ ! -s "$snapshot_file" ]; then
            log_error "Downloaded Qdrant snapshot is missing or empty: $snapshot_file"
            exit 1
        fi
        log_info "Qdrant snapshot downloaded to $snapshot_file"
    }

    if [ -n "${QDRANT_COLLECTION_OVERRIDE_SET}" ]; then
        # Respect explicit operator override.
        backup_qdrant_collection "$QDRANT_COLLECTION"
    else
        # Default behavior: capture both current and legacy collections if present.
        backup_qdrant_collection "$QDRANT_COLLECTION"
        if [ "$QDRANT_LEGACY_COLLECTION" != "$QDRANT_COLLECTION" ]; then
            backup_qdrant_collection "$QDRANT_LEGACY_COLLECTION"
        fi
    fi
fi

# -----------------------------------------------------------------------------
# 2. Docker Volume Backups
# -----------------------------------------------------------------------------
log_info "Backing up Docker volumes..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    log_error "Docker not found - cannot backup volumes"
    exit 1
fi

# Backup Neo4j volume
if docker volume inspect "$NEO4J_VOLUME" > /dev/null 2>&1; then
    log_info "Backing up Neo4j volume: $NEO4J_VOLUME"
    docker run --rm \
        -v "${NEO4J_VOLUME}:/source:ro" \
        -v "$(cd "$BACKUP_DIR" && pwd):/backup" \
        alpine tar czf /backup/neo4j_data.tar.gz -C /source .
    log_info "Neo4j backup complete: ${BACKUP_DIR}/neo4j_data.tar.gz"
else
    log_warn "Neo4j volume '$NEO4J_VOLUME' not found - skipping"
fi

# Backup Qdrant volume
if docker volume inspect "$QDRANT_VOLUME" > /dev/null 2>&1; then
    log_info "Backing up Qdrant volume: $QDRANT_VOLUME"
    docker run --rm \
        -v "${QDRANT_VOLUME}:/source:ro" \
        -v "$(cd "$BACKUP_DIR" && pwd):/backup" \
        alpine tar czf /backup/qdrant_data.tar.gz -C /source .
    log_info "Qdrant backup complete: ${BACKUP_DIR}/qdrant_data.tar.gz"
else
    log_warn "Qdrant volume '$QDRANT_VOLUME' not found - skipping"
fi

# -----------------------------------------------------------------------------
# 3. Backup uploads directory (source documents)
# -----------------------------------------------------------------------------
UPLOADS_DIR="./uploads"
if [ -d "$UPLOADS_DIR" ]; then
    log_info "Backing up uploads directory..."
    tar czf "${BACKUP_DIR}/uploads.tar.gz" -C "$(dirname "$UPLOADS_DIR")" "$(basename "$UPLOADS_DIR")"
    log_info "Uploads backup complete: ${BACKUP_DIR}/uploads.tar.gz"
else
    log_warn "Uploads directory not found at $UPLOADS_DIR"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
log_info "========================================="
log_info "Backup complete!"
log_info "========================================="
log_info "Location: $BACKUP_DIR"
echo ""
ls -lh "$BACKUP_DIR"
echo ""
log_info "To restore, see: ./scripts/restore.sh (if available)"
