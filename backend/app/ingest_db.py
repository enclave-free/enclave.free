"""
Enclave Ingest Database Module
Handles SQLite persistence for ingest jobs and chunks.

This module provides Create and Read operations for ingest job state.
The data is stored in SQLite (which is volume-mounted) rather than JSON files,
ensuring job state survives container rebuilds.

TODO (Future CRUD operations):
- Update: update_job_status(), update_chunk_status()
- Delete: delete_job(), delete_chunks_for_job(), purge_old_jobs()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import content_artifacts
from database import get_connection, get_cursor

logger = logging.getLogger("enclave.ingest_db")


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================

def init_ingest_schema():
    """
    Initialize ingest-related tables in SQLite.
    Call this on app startup (from database.init_schema or separately).
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Ingest jobs table - tracks document processing jobs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingest_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            ontology_id TEXT NOT NULL,
            sample_percent REAL DEFAULT 100.0,
            canonical_name TEXT,
            replacement_for_job_id TEXT,
            replaced_by_job_id TEXT,
            is_current INTEGER DEFAULT 1,
            content_sha256 TEXT,
            total_chunks INTEGER DEFAULT 0,
            processed_chunks INTEGER DEFAULT 0,
            failed_chunks INTEGER DEFAULT 0,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ingest chunks table - tracks individual chunk processing
    # NOTE: For MVP, we may not need to persist all chunk details.
    # The chunks table is optional - uncomment if needed for resumable ingestion.
    #
    # cursor.execute("""
    #     CREATE TABLE IF NOT EXISTS ingest_chunks (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         chunk_id TEXT UNIQUE NOT NULL,
    #         job_id TEXT NOT NULL,
    #         chunk_index INTEGER NOT NULL,
    #         status TEXT NOT NULL DEFAULT 'pending',
    #         source_file TEXT NOT NULL,
    #         char_count INTEGER DEFAULT 0,
    #         error TEXT,
    #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #         FOREIGN KEY (job_id) REFERENCES ingest_jobs(job_id) ON DELETE CASCADE
    #     )
    # """)

    conn.commit()
    cursor.close()

    _migrate_add_replacement_columns()

    # Index for faster job lookups by status. Keep this after migrations so
    # upgraded SQLite volumes have replacement columns before indexes use them.
    cursor = conn.cursor()
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status ON ingest_jobs(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_canonical_current
        ON ingest_jobs(canonical_name, is_current)
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS retrieval_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT UNIQUE NOT NULL,
            job_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            char_count INTEGER DEFAULT 0,
            encrypted_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES ingest_jobs(job_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_job_id
        ON retrieval_chunks(job_id)
    """)

    conn.commit()
    cursor.close()
    logger.info("Ingest schema initialized")


def _migrate_add_replacement_columns() -> None:
    """Add document replacement lifecycle columns to existing ingest_jobs tables."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(ingest_jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    migrations = {
        "canonical_name": "ALTER TABLE ingest_jobs ADD COLUMN canonical_name TEXT",
        "replacement_for_job_id": "ALTER TABLE ingest_jobs ADD COLUMN replacement_for_job_id TEXT",
        "replaced_by_job_id": "ALTER TABLE ingest_jobs ADD COLUMN replaced_by_job_id TEXT",
        "is_current": "ALTER TABLE ingest_jobs ADD COLUMN is_current INTEGER DEFAULT 1",
        "content_sha256": "ALTER TABLE ingest_jobs ADD COLUMN content_sha256 TEXT",
    }

    for column, sql in migrations.items():
        if column not in columns:
            cursor.execute(sql)
            logger.info(f"Migration: Added '{column}' column to ingest_jobs")

    cursor.execute("""
        UPDATE ingest_jobs
        SET canonical_name = filename
        WHERE canonical_name IS NULL OR canonical_name = ''
    """)
    cursor.execute("""
        UPDATE ingest_jobs
        SET is_current = 1
        WHERE is_current IS NULL
    """)
    conn.commit()
    cursor.close()


# =============================================================================
# CREATE OPERATIONS
# =============================================================================

def create_job(
    job_id: str,
    filename: str,
    file_path: str,
    ontology_id: str,
    sample_percent: float = 100.0,
    canonical_name: str | None = None,
    replacement_for_job_id: str | None = None,
    content_sha256: str | None = None,
    is_current: bool = True,
) -> int:
    """
    Create a new ingest job record.
    
    Args:
        job_id: Unique job identifier (hash)
        filename: Original uploaded filename
        file_path: Path to saved file
        ontology_id: Ontology used for extraction
        sample_percent: Percentage of chunks to process (for testing)
        canonical_name: Optional operator-facing document name. Defaults to filename when omitted.
        replacement_for_job_id: Optional job ID this job is replacing. Defaults to None.
        content_sha256: Optional SHA-256 digest of the uploaded content. Defaults to None.
        is_current: Whether this job is the active current document. Defaults to True and is stored as 1/0.
    
    Returns:
        SQLite row ID of created job
    """
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO ingest_jobs (
                job_id, filename, file_path, ontology_id, sample_percent,
                canonical_name, replacement_for_job_id, is_current, content_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            filename,
            file_path,
            ontology_id,
            sample_percent,
            canonical_name or filename,
            replacement_for_job_id,
            int(is_current),
            content_sha256,
        ))
        logger.info(f"Created ingest job: {job_id} ({filename})")
        return cursor.lastrowid


def upsert_retrieval_chunk(
    *,
    chunk_id: str,
    job_id: str,
    chunk_index: int,
    source_file: str,
    text: str,
) -> None:
    """Persist retrieval chunk text encrypted for backend hydration."""
    stored_text = content_artifacts.encode_for_storage(text.encode("utf-8")).decode("utf-8")
    now = datetime.utcnow().isoformat()
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO retrieval_chunks (
                chunk_id, job_id, chunk_index, source_file, char_count, encrypted_text, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                job_id = excluded.job_id,
                chunk_index = excluded.chunk_index,
                source_file = excluded.source_file,
                char_count = excluded.char_count,
                encrypted_text = excluded.encrypted_text,
                updated_at = excluded.updated_at
        """, (
            chunk_id,
            job_id,
            chunk_index,
            source_file,
            len(text),
            stored_text,
            now,
            now,
        ))


# =============================================================================
# READ OPERATIONS
# =============================================================================

def get_job(job_id: str) -> Optional[dict]:
    """
    Get a single job by job_id.
    
    Returns:
        Job dict or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingest_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    cursor.close()
    
    if row:
        return dict(row)
    return None


def get_retrieval_chunk(chunk_id: str) -> Optional[dict]:
    """Return one retrieval chunk with decrypted text."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM retrieval_chunks WHERE chunk_id = ?", (chunk_id,))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return None
    chunk = dict(row)
    try:
        chunk["text"] = content_artifacts.decrypt_bytes(chunk["encrypted_text"].encode("utf-8")).decode("utf-8")
    except Exception as exc:
        chunk["text"] = None
        chunk["decryption_error"] = {
            "type": type(exc).__name__,
            "msg": str(exc),
        }
    return chunk


def list_retrieval_chunks(job_id: str, limit: int | None = None) -> list[dict]:
    """List raw encrypted retrieval chunk rows for one document job."""
    conn = get_connection()
    cursor = conn.cursor()
    if limit is None:
        cursor.execute(
            "SELECT * FROM retrieval_chunks WHERE job_id = ? ORDER BY chunk_index ASC, id ASC",
            (job_id,),
        )
    else:
        bounded_limit = max(0, int(limit))
        cursor.execute(
            "SELECT * FROM retrieval_chunks WHERE job_id = ? ORDER BY chunk_index ASC, id ASC LIMIT ?",
            (job_id, bounded_limit),
        )
    rows = cursor.fetchall()
    cursor.close()
    return [dict(row) for row in rows]


def list_jobs(status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """
    List all ingest jobs, optionally filtered by status.
    
    Args:
        status: Filter by status (e.g., 'completed', 'pending')
        limit: Max number of jobs to return
        offset: Number of sorted jobs to skip
    
    Returns:
        List of job dicts
    """
    limit = max(0, min(int(limit), 1000))
    offset = max(0, int(offset))
    conn = get_connection()
    cursor = conn.cursor()
    
    if status:
        cursor.execute(
            "SELECT * FROM ingest_jobs WHERE status = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (status, limit, offset)
        )
    else:
        cursor.execute(
            "SELECT * FROM ingest_jobs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
    
    rows = cursor.fetchall()
    cursor.close()
    return [dict(row) for row in rows]


def list_completed_jobs() -> list[dict]:
    """
    List all completed jobs (for document selector UI).
    Includes both 'completed' and 'completed_with_errors' statuses.
    
    Returns:
        List of job dicts that have finished processing
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ingest_jobs 
        WHERE status IN ('completed', 'completed_with_errors')
          AND is_current = 1
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    return [dict(row) for row in rows]


def job_exists(job_id: str) -> bool:
    """Check if a job exists by job_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM ingest_jobs WHERE job_id = ?", (job_id,))
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists


def get_current_job_by_canonical_name(canonical_name: str) -> Optional[dict]:
    """Get the current completed job for a canonical document name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ingest_jobs
        WHERE canonical_name = ?
          AND is_current = 1
          AND status IN ('completed', 'completed_with_errors')
        ORDER BY created_at DESC
        LIMIT 1
    """, (canonical_name,))
    row = cursor.fetchone()
    cursor.close()
    return dict(row) if row else None


def get_inflight_replacement_by_canonical_name(canonical_name: str) -> Optional[dict]:
    """Get a pending/processing replacement for a canonical document name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ingest_jobs
        WHERE canonical_name = ?
          AND replacement_for_job_id IS NOT NULL
          AND status IN ('pending', 'processing')
        ORDER BY created_at DESC
        LIMIT 1
    """, (canonical_name,))
    row = cursor.fetchone()
    cursor.close()
    return dict(row) if row else None


def list_current_jobs(limit: int = 500) -> list[dict]:
    """List current completed jobs only."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ingest_jobs
        WHERE is_current = 1
          AND status IN ('completed', 'completed_with_errors')
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(row) for row in rows]


# =============================================================================
# UPDATE OPERATIONS
# =============================================================================

def update_job_status(
    job_id: str,
    status: str,
    total_chunks: Optional[int] = None,
    processed_chunks: Optional[int] = None,
    failed_chunks: Optional[int] = None,
    error: Optional[str] = None,
) -> bool:
    """
    Update job status and progress counters.
    
    Args:
        job_id: Job to update
        status: New status value
        total_chunks: Total chunks (set once after chunking)
        processed_chunks: Number of successfully processed chunks
        failed_chunks: Number of failed chunks
        error: Error message if failed
    
    Returns:
        True if job was updated, False if not found
    """
    with get_cursor() as cursor:
        # Build dynamic SET clause
        updates = ["status = ?", "updated_at = ?"]
        params = [status, datetime.utcnow().isoformat()]
        
        if total_chunks is not None:
            updates.append("total_chunks = ?")
            params.append(total_chunks)
        if processed_chunks is not None:
            updates.append("processed_chunks = ?")
            params.append(processed_chunks)
        if failed_chunks is not None:
            updates.append("failed_chunks = ?")
            params.append(failed_chunks)
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        
        params.append(job_id)
        
        cursor.execute(
            f"UPDATE ingest_jobs SET {', '.join(updates)} WHERE job_id = ?",
            params
        )
        return cursor.rowcount > 0


def promote_replacement(new_job_id: str, old_job_id: str) -> bool:
    """Mark a successful replacement as current and retire the old job."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM ingest_jobs WHERE job_id IN (?, ?)",
            (new_job_id, old_job_id),
        )
        if cursor.fetchone()["count"] != 2:
            raise ValueError("Both replacement jobs must exist before promotion")

        cursor.execute("""
            UPDATE ingest_jobs
            SET is_current = 0,
                replaced_by_job_id = ?,
                updated_at = ?
            WHERE job_id = ?
        """, (new_job_id, datetime.utcnow().isoformat(), old_job_id))
        old_updated = cursor.rowcount > 0

        cursor.execute("""
            UPDATE ingest_jobs
            SET is_current = 1,
                updated_at = ?
            WHERE job_id = ?
        """, (datetime.utcnow().isoformat(), new_job_id))
        new_updated = cursor.rowcount > 0

        if not old_updated or not new_updated:
            raise RuntimeError("Failed to atomically promote replacement jobs")

        return old_updated and new_updated


# =============================================================================
# DELETE OPERATIONS
# =============================================================================

def delete_job(job_id: str) -> bool:
    """
    Delete a job from ingest_jobs table.

    Note: CASCADE on foreign keys automatically handles deletion
    from document_defaults and document_defaults_user_type_overrides tables.

    Args:
        job_id: Job to delete

    Returns:
        True if job was deleted, False if not found
    """
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM ingest_jobs WHERE job_id = ?", (job_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted ingest job: {job_id}")
        return deleted


def delete_retrieval_chunks_for_job(job_id: str) -> int:
    """Delete encrypted retrieval chunk text rows for one document job."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM retrieval_chunks WHERE job_id = ?", (job_id,))
        return cursor.rowcount


def purge_old_jobs(days: int = 30) -> int:
    """Delete ingest jobs older than the cutoff. Returns count deleted."""
    days = int(days)
    if days < 0:
        raise ValueError("days must be greater than or equal to 0")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM ingest_jobs WHERE created_at < ?", (cutoff,))
        deleted = cursor.rowcount
        if deleted:
            logger.info(f"Purged {deleted} ingest jobs older than {days} days")
        return deleted
