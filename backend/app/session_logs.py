"""
Session Logs — captured chat transcripts for the Test & Feedback module.

Sensitive by default: a transcript is NIP-04 encrypted to the admin pubkey
*before* it touches disk, so the control plane persists only ciphertext (plus the
ephemeral pubkey the admin needs to decrypt client-side via NIP-07). The backend
can never read a transcript back in plaintext — see encryption.encrypt_for_admin.

General by design: `source` distinguishes an admin testing as a user persona
('admin_test') from a real user's logged session ('user'), so the same storage +
review pathway serves both without re-architecting.

Layout:
- metadata rows live in the session_logs / session_log_feedback tables
- the transcript ciphertext lives in a file at <data dir>/session_logs/<log_id>.json
- the DB row points at that file and carries the ephemeral pubkey for decryption
"""

from __future__ import annotations

import json
import logging
import os
import uuid
import zipfile
from io import BytesIO
from typing import Any, Optional

import database
from encryption import encrypt_for_admin_required, get_admin_pubkey

logger = logging.getLogger("enclave.session_logs")

VALID_SOURCES = ("admin_test", "user")
VALID_RATINGS = ("up", "down")


def _transcripts_dir() -> str:
    base = os.path.dirname(database.SQLITE_PATH) or "."
    path = os.path.join(base, "session_logs")
    os.makedirs(path, exist_ok=True)
    return path


def _transcript_file(log_id: str) -> str:
    # log_id is a server-generated uuid hex; safe as a filename.
    return os.path.join(_transcripts_dir(), f"{log_id}.json")


def _new_log_id() -> str:
    return uuid.uuid4().hex


def _row_to_metadata(row: Any) -> dict[str, Any]:
    """Public metadata for a log row — never includes transcript content."""
    return {
        "log_id": row["log_id"],
        "source": row["source"],
        "title": row["title"],
        "subject_user_id": row["subject_user_id"],
        "user_type_id": row["user_type_id"],
        "sage_session_id": row["sage_session_id"],
        "turn_count": row["turn_count"],
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "has_transcript": bool(row["transcript_path"]),
    }


def _turn_metadata_json(turns: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {"turn_index": index, "role": str(turn.get("role", ""))}
            for index, turn in enumerate(turns)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _assistant_turn_indexes(row: Any) -> set[int]:
    raw_metadata = row["turn_metadata_json"]
    if not raw_metadata:
        raise ValueError("Transcript turn metadata is unavailable")
    try:
        metadata = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise ValueError("Transcript turn metadata is invalid") from exc

    assistant_indexes: set[int] = set()
    for item in metadata:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "assistant":
            try:
                assistant_indexes.add(int(item["turn_index"]))
            except (KeyError, TypeError, ValueError):
                continue
    return assistant_indexes


def create_session_log(
    *,
    source: str = "admin_test",
    title: Optional[str] = None,
    subject_user_id: Optional[int] = None,
    user_type_id: Optional[int] = None,
    sage_session_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict[str, Any]:
    """Open a new (active) session log. Transcript is saved later via save_transcript."""
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid session log source: {source}")

    log_id = _new_log_id()
    with database.get_cursor() as cursor:
        cursor.execute(
            """INSERT INTO session_logs (
                log_id, source, title, subject_user_id, user_type_id,
                sage_session_id, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id,
                source,
                title,
                subject_user_id,
                user_type_id,
                sage_session_id,
                created_by,
            ),
        )
    return get_session_log_metadata(log_id)  # type: ignore[return-value]


def save_transcript(
    log_id: str,
    turns: list[dict[str, Any]],
    *,
    created_by: Optional[str] = None,
) -> dict[str, Any]:
    """Encrypt the transcript to the admin pubkey, write the ciphertext to disk,
    and mark the log completed. Fails closed: raises if no admin is configured,
    so a transcript is never written in plaintext."""
    admin_pubkey = get_admin_pubkey()
    if not admin_pubkey:
        raise ValueError("No admin configured for encryption")
    if _get_row(log_id) is None:
        raise KeyError(log_id)

    plaintext = json.dumps({"turns": turns}, ensure_ascii=False)
    ciphertext, ephemeral_pubkey = encrypt_for_admin_required(plaintext)
    turn_metadata = _turn_metadata_json(turns)

    path = _transcript_file(log_id)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(ciphertext)

        now = database.utc_timestamp_z()
        with database.get_cursor() as cursor:
            cursor.execute(
                """UPDATE session_logs
                   SET transcript_path = ?,
                       transcript_ephemeral_pubkey = ?,
                       encrypted_to_pubkey = ?,
                       turn_metadata_json = ?,
                       turn_count = ?,
                       status = 'completed',
                       completed_at = ?,
                       updated_at = ?
                   WHERE log_id = ?""",
                (
                    path,
                    ephemeral_pubkey,
                    admin_pubkey,
                    turn_metadata,
                    len(turns),
                    now,
                    now,
                    log_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(log_id)
    except Exception:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("Could not remove failed transcript file for %s", log_id, exc_info=True)
        raise
    logger.info("Saved encrypted transcript for session log %s (%d turns)", log_id, len(turns))
    return get_session_log_metadata(log_id)  # type: ignore[return-value]


def list_session_logs(
    *,
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List session-log metadata (no transcript content), newest first."""
    clauses = []
    params: list[Any] = []
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 500)))
    with database.get_cursor() as cursor:
        cursor.execute(
            f"""SELECT * FROM session_logs
                {where}
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?""",
            params,
        )
        return [_row_to_metadata(row) for row in cursor.fetchall()]


def _get_row(log_id: str) -> Any:
    with database.get_cursor() as cursor:
        cursor.execute("SELECT * FROM session_logs WHERE log_id = ?", (log_id,))
        return cursor.fetchone()


def get_session_log_metadata(log_id: str) -> Optional[dict[str, Any]]:
    row = _get_row(log_id)
    return _row_to_metadata(row) if row else None


def get_session_log(log_id: str) -> Optional[dict[str, Any]]:
    """Full log for admin review: metadata + the encrypted transcript ciphertext
    (for client-side NIP-07 decryption) + per-turn feedback. The backend does NOT
    decrypt — it hands the admin the ciphertext and the ephemeral pubkey."""
    row = _get_row(log_id)
    if not row:
        return None

    transcript_ciphertext: Optional[str] = None
    if row["transcript_path"]:
        try:
            with open(row["transcript_path"], "r", encoding="utf-8") as handle:
                transcript_ciphertext = handle.read()
        except OSError:
            logger.warning("Transcript file missing for session log %s", log_id, exc_info=True)

    data = _row_to_metadata(row)
    data["transcript_ciphertext"] = transcript_ciphertext
    data["transcript_ephemeral_pubkey"] = row["transcript_ephemeral_pubkey"]
    data["encrypted_to_pubkey"] = row["encrypted_to_pubkey"]
    data["feedback"] = list_feedback(log_id)
    return data


def delete_session_log(log_id: str) -> bool:
    """Delete a session log, its feedback (cascade), and its transcript file."""
    row = _get_row(log_id)
    if not row:
        return False
    if row["transcript_path"]:
        try:
            os.remove(row["transcript_path"])
        except OSError:
            logger.warning("Could not remove transcript file for %s", log_id, exc_info=True)
            raise
    with database.get_cursor() as cursor:
        cursor.execute("DELETE FROM session_logs WHERE log_id = ?", (log_id,))
        return cursor.rowcount > 0


def export_session_log_zip(
    log_id: str,
    *,
    changed_by: Optional[str] = None,
) -> tuple[str, bytes]:
    """Build a copied export bundle for one completed session log.

    The bundle intentionally carries encrypted transcript/comment material and
    the metadata needed for client-side decryption, never plaintext content.
    """
    detail = get_session_log(log_id)
    if detail is None:
        raise KeyError(log_id)
    if not detail["transcript_ciphertext"]:
        raise ValueError("Session log has no transcript to export")

    exported_at = database.utc_timestamp_z()
    metadata = {
        "log_id": detail["log_id"],
        "source": detail["source"],
        "title": detail["title"],
        "subject_user_id": detail["subject_user_id"],
        "user_type_id": detail["user_type_id"],
        "sage_session_id": detail["sage_session_id"],
        "turn_count": detail["turn_count"],
        "status": detail["status"],
        "created_by": detail["created_by"],
        "created_at": detail["created_at"],
        "updated_at": detail["updated_at"],
        "completed_at": detail["completed_at"],
        "has_transcript": detail["has_transcript"],
        "transcript_ephemeral_pubkey": detail["transcript_ephemeral_pubkey"],
        "encrypted_to_pubkey": detail["encrypted_to_pubkey"],
        "copied_export": True,
        "lifecycle_posture": "outside_active_storage_lifecycle",
        "exported_at": exported_at,
    }

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        )
        zip_file.writestr("transcript.nip04.txt", detail["transcript_ciphertext"])
        zip_file.writestr(
            "feedback.json",
            json.dumps(detail["feedback"], ensure_ascii=False, indent=2, sort_keys=True),
        )

    database.log_config_audit_event(
        table_name="data_deletion",
        config_key="copied_export:test_feedback_session",
        old_value=None,
        new_value=json.dumps(
            {
                "workflow": "copied_export",
                "target": "test_feedback_session",
                "lifecycle_posture": "outside_active_storage_lifecycle",
                "log_id": log_id,
                "filename": f"test_feedback_{log_id}.zip",
                "exported_at": exported_at,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        changed_by=changed_by or "unknown",
    )
    return f"test_feedback_{log_id}.zip", archive.getvalue()


def _feedback_to_dict(row: Any) -> dict[str, Any]:
    return {
        "turn_index": row["turn_index"],
        "rating": row["rating"],
        "comment_ciphertext": row["comment_ciphertext"],
        "comment_ephemeral_pubkey": row["comment_ephemeral_pubkey"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_feedback(log_id: str) -> list[dict[str, Any]]:
    with database.get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM session_log_feedback WHERE log_id = ? ORDER BY turn_index",
            (log_id,),
        )
        return [_feedback_to_dict(row) for row in cursor.fetchall()]


def set_turn_feedback(
    log_id: str,
    turn_index: int,
    rating: str,
    *,
    comment: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict[str, Any]:
    """Upsert per-turn feedback. Rating is stored plaintext (for querying); the
    optional comment is NIP-04 encrypted to the admin pubkey (it may quote
    transcript content)."""
    if rating not in VALID_RATINGS:
        raise ValueError(f"Invalid rating: {rating}")
    row = _get_row(log_id)
    if row is None:
        raise KeyError(log_id)
    if turn_index not in _assistant_turn_indexes(row):
        raise ValueError("Feedback can only be saved for assistant turns")

    comment_ciphertext: Optional[str] = None
    comment_ephemeral_pubkey: Optional[str] = None
    trimmed = comment.strip() if comment else None
    if trimmed:
        comment_ciphertext, comment_ephemeral_pubkey = encrypt_for_admin_required(trimmed)

    now = database.utc_timestamp_z()
    with database.get_cursor() as cursor:
        cursor.execute(
            """INSERT INTO session_log_feedback (
                log_id, turn_index, rating, comment_ciphertext,
                comment_ephemeral_pubkey, created_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(log_id, turn_index) DO UPDATE SET
                rating = excluded.rating,
                comment_ciphertext = excluded.comment_ciphertext,
                comment_ephemeral_pubkey = excluded.comment_ephemeral_pubkey,
                created_by = excluded.created_by,
                updated_at = excluded.updated_at""",
            (
                log_id,
                turn_index,
                rating,
                comment_ciphertext,
                comment_ephemeral_pubkey,
                created_by,
                now,
            ),
        )
    with database.get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM session_log_feedback WHERE log_id = ? AND turn_index = ?",
            (log_id, turn_index),
        )
        return _feedback_to_dict(cursor.fetchone())
