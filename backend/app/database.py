"""
Enclave Database Module
Handles SQLite connection and schema for user/admin management.
"""

from __future__ import annotations

import json
import os
import sqlite3
import logging
import hashlib
import hmac
import re
import contextvars
from typing import Iterator
from contextlib import contextmanager
from base64 import b64encode, b64decode
from datetime import datetime, timedelta, timezone
from Crypto.Cipher import AES
from models import RESOURCE_CONTACT_KEYS
from region_data import is_valid_scope

# Configure logging
logger = logging.getLogger("enclave.database")

# Configuration
SQLITE_PATH = os.getenv("SQLITE_PATH", "/data/enclave.db")


def utc_timestamp_z() -> str:
    """Return a second-precision UTC timestamp with an explicit Z suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dumps_for_lifecycle(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        logger.warning(
            "Lifecycle JSON contained non-standard values; serializing with string fallbacks",
            exc_info=True,
        )
        return json.dumps(value, sort_keys=True, default=str)

# Lazy-loaded connection
_connection = None
_dedicated_connection: contextvars.ContextVar[sqlite3.Connection | None] = contextvars.ContextVar(
    "dedicated_connection",
    default=None,
)
_deployment_secret_key = None
_audit_hmac_key = None

# Deployment secret encryption format:
# enc::v1::<base64_nonce>:<base64_tag>:<base64_ciphertext>
DEPLOYMENT_SECRET_PREFIX = "enc::v1::"
DEPLOYMENT_SECRET_NONCE_BYTES = 12


def get_connection():
    """Get or create SQLite connection"""
    dedicated = _dedicated_connection.get()
    if dedicated is not None:
        return dedicated

    global _connection
    if _connection is None:
        # Ensure directory exists
        db_dir = os.path.dirname(SQLITE_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        _connection = _configure_connection(sqlite3.connect(SQLITE_PATH, check_same_thread=False))
        logger.info(f"Connected to SQLite database: {SQLITE_PATH}")
    return _connection


def _configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


@contextmanager
def dedicated_connection() -> Iterator[sqlite3.Connection]:
    """Use a per-task SQLite connection for background work."""
    conn = _configure_connection(sqlite3.connect(SQLITE_PATH, check_same_thread=False))
    token = _dedicated_connection.set(conn)
    try:
        yield conn
    finally:
        _dedicated_connection.reset(token)
        conn.close()


@contextmanager
def get_cursor():
    """Context manager for database cursor with auto-commit"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


@contextmanager
def get_write_cursor() -> Iterator[sqlite3.Cursor]:
    """Context manager that acquires a write lock via BEGIN IMMEDIATE.

    Use this instead of get_cursor() when the transaction includes
    _insert_config_audit_log, which requires serialized access to the
    hash chain to prevent concurrent writers from forking it.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def _get_deployment_secret_key() -> bytes:
    """
    Derive a stable symmetric key for deployment secret encryption.
    Uses the same SECRET_KEY root as auth/session signing.
    """
    global _deployment_secret_key
    if _deployment_secret_key is None:
        from auth import SECRET_KEY
        _deployment_secret_key = hashlib.sha256(
            f"enclave-deployment-config:{SECRET_KEY}".encode("utf-8")
        ).digest()
    return _deployment_secret_key


def _get_audit_hmac_key() -> bytes:
    """Load and cache the secret key used for audit-chain HMACs."""
    global _audit_hmac_key
    if _audit_hmac_key is None:
        from auth import SECRET_KEY

        if not SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be configured to compute config audit HMAC hashes")
        _audit_hmac_key = SECRET_KEY.encode("utf-8")
    return _audit_hmac_key


def _compute_audit_entry_hash(payload: str) -> str:
    """Compute deterministic HMAC-SHA256 hash for an audit-chain payload."""
    return hmac.new(_get_audit_hmac_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_deployment_secret_encrypted(value: str | None) -> bool:
    """Check if a deployment secret value is already encrypted."""
    return bool(value) and isinstance(value, str) and value.startswith(DEPLOYMENT_SECRET_PREFIX)


def _encrypt_deployment_secret_value(value: str) -> str:
    """Encrypt deployment secret value using AES-256-GCM."""
    if _is_deployment_secret_encrypted(value):
        return value

    nonce = os.urandom(DEPLOYMENT_SECRET_NONCE_BYTES)
    cipher = AES.new(_get_deployment_secret_key(), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(value.encode("utf-8"))
    return (
        f"{DEPLOYMENT_SECRET_PREFIX}"
        f"{b64encode(nonce).decode('ascii')}:"
        f"{b64encode(tag).decode('ascii')}:"
        f"{b64encode(ciphertext).decode('ascii')}"
    )


def _decrypt_deployment_secret_value(value: str) -> str:
    """Decrypt deployment secret value (returns input unchanged if plaintext)."""
    if not _is_deployment_secret_encrypted(value):
        return value

    encoded = value[len(DEPLOYMENT_SECRET_PREFIX):]
    parts = encoded.split(":", 2)
    if len(parts) != 3:
        raise ValueError("Invalid encrypted deployment secret format")

    nonce = b64decode(parts[0].encode("ascii"))
    tag = b64decode(parts[1].encode("ascii"))
    ciphertext = b64decode(parts[2].encode("ascii"))

    cipher = AES.new(_get_deployment_secret_key(), AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext.decode("utf-8")


def init_schema():
    """Initialize database schema"""
    conn = get_connection()
    cursor = conn.cursor()

    # Admins table - stores single Nostr pubkey (max 1 admin per instance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pubkey TEXT UNIQUE NOT NULL,
            session_nonce INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Instance state - tracks setup completion and governance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instance_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Initialize instance state if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO instance_state (key, value)
        VALUES ('setup_complete', 'false')
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO instance_state (key, value)
        VALUES ('admin_initialized', 'false')
    """)

    # Fix for upgraded installs: if admins already exist, ensure admin_initialized is true
    # This handles cases where the DB was created before instance_state tracking was added
    cursor.execute("SELECT COUNT(*) FROM admins")
    admin_count = cursor.fetchone()[0]
    if admin_count > 0:
        cursor.execute("""
            UPDATE instance_state SET value = 'true', updated_at = CURRENT_TIMESTAMP
            WHERE key = 'admin_initialized' AND value = 'false'
        """)
        if cursor.rowcount > 0:
            logger.info("Migration: Fixed admin_initialized state for existing admin")

    # Instance settings - key-value store for admin configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instance_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # User types - groups of users with different question sets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # User field definitions - admin-defined custom fields for users
    # user_type_id: NULL = global field (shown for all types), non-NULL = type-specific
    # encryption_enabled: 1 = encrypt field values (default), 0 = store plaintext
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_field_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL,
            required INTEGER DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            user_type_id INTEGER,
            encryption_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_type_id) REFERENCES user_types(id) ON DELETE CASCADE,
            UNIQUE(field_name, user_type_id)
        )
    """)

    # Users table
    # Note: email and name are encrypted using NIP-04
    # - encrypted_email/encrypted_name: NIP-04 ciphertext
    # - ephemeral_pubkey_email/name: pubkey for decryption
    # - email_blind_index: HMAC hash for email lookups
    # email/name are deprecated compatibility columns; current writes keep them NULL.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pubkey TEXT UNIQUE,
            email TEXT,
            name TEXT,
            encrypted_email TEXT,
            ephemeral_pubkey_email TEXT,
            email_blind_index TEXT,
            encrypted_name TEXT,
            ephemeral_pubkey_name TEXT,
            user_type_id INTEGER,
            approved INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_type_id) REFERENCES user_types(id)
        )
    """)

    # User field values - dynamic field storage (EAV pattern)
    # Note: values are encrypted using NIP-04
    # - encrypted_value: NIP-04 ciphertext
    # - ephemeral_pubkey: pubkey for decryption
    # value is used only for operator-selected plaintext fields.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_field_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            field_id INTEGER NOT NULL,
            value TEXT,
            encrypted_value TEXT,
            ephemeral_pubkey TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (field_id) REFERENCES user_field_definitions(id) ON DELETE CASCADE,
            UNIQUE(user_id, field_id)
        )
    """)

    # Create indexes for performance (note: email_blind_index index created in migration)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_field_values_user ON user_field_values(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_field_values_field ON user_field_values(field_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_field_definitions_type ON user_field_definitions(user_type_id)")
    # Note: idx_user_field_definitions_encryption created in _migrate_add_encryption_enabled_column()

    # Agent Settings table. The ai_config name is shared with Sage's current schema.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'string',
            category TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Document defaults table - controls document availability and default state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_defaults (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            is_available INTEGER DEFAULT 1,
            is_default_active INTEGER DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES ingest_jobs(job_id) ON DELETE CASCADE
        )
    """)

    # Deployment configuration table - manages environment settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deployment_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            is_secret INTEGER DEFAULT 0,
            requires_restart INTEGER DEFAULT 0,
            category TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inference_verification_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_identity TEXT NOT NULL,
            provider_endpoint TEXT NOT NULL,
            model_identifier TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
            trigger TEXT NOT NULL,
            expected_claims_fingerprint TEXT NOT NULL,
            actual_claims_fingerprint TEXT,
            verifier_version TEXT NOT NULL,
            failure_category TEXT,
            failure_message TEXT,
            encrypted_attestation_material TEXT,
            checked_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inference_verification_current
        ON inference_verification_records (
            provider_identity,
            provider_endpoint,
            model_identifier,
            expected_claims_fingerprint,
            status,
            checked_at DESC
        )
    """)

    # Config audit log table - tracks all configuration changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            config_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            prev_hash TEXT,
            entry_hash TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deletion_tombstones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_data_class TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            former_subject_ref TEXT,
            status TEXT NOT NULL CHECK(status IN ('incomplete', 'completed')),
            source TEXT NOT NULL,
            workflow TEXT NOT NULL,
            deletion JSON NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS retention_run_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT NOT NULL CHECK(trigger IN ('manual', 'machine')),
            actor TEXT NOT NULL,
            status TEXT NOT NULL,
            policy_snapshot JSON NOT NULL,
            counts JSON NOT NULL,
            results JSON NOT NULL,
            tombstone_refs JSON NOT NULL,
            audit_log_id INTEGER,
            audit_entry_hash TEXT,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_retention_run_records_created
        ON retention_run_records(created_at DESC, id DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_retention_run_records_trigger_created
        ON retention_run_records(trigger, created_at DESC, id DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_deletion_tombstones_status
        ON deletion_tombstones(status, updated_at DESC)
    """)
    cursor.execute("""
        DELETE FROM deletion_tombstones
        WHERE status = 'incomplete'
          AND id NOT IN (
              SELECT MAX(id)
              FROM deletion_tombstones
              WHERE status = 'incomplete'
              GROUP BY conversation_id
          )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_deletion_tombstones_incomplete_conversation
        ON deletion_tombstones(conversation_id)
        WHERE status = 'incomplete'
    """)

    # Agent Settings user-type overrides. The table name is shared with Sage's current schema.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_config_user_type_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_config_key TEXT NOT NULL,
            user_type_id INTEGER NOT NULL,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_type_id) REFERENCES user_types(id) ON DELETE CASCADE,
            UNIQUE(ai_config_key, user_type_id)
        )
    """)

    # Document defaults user-type overrides - stores per-user-type document defaults
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_defaults_user_type_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            user_type_id INTEGER NOT NULL,
            is_available INTEGER,
            is_default_active INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES ingest_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (user_type_id) REFERENCES user_types(id) ON DELETE CASCADE,
            UNIQUE(job_id, user_type_id)
        )
    """)

    # Indexes for user-type override tables
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_config_overrides_type ON ai_config_user_type_overrides(user_type_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_config_overrides_key ON ai_config_user_type_overrides(ai_config_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_defaults_overrides_type ON document_defaults_user_type_overrides(user_type_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_defaults_overrides_job ON document_defaults_user_type_overrides(job_id)")

    # Sage-owned durable context for low-sensitivity User Memory.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            normalized_kind TEXT NOT NULL,
            normalized_content TEXT NOT NULL,
            importance INTEGER NOT NULL DEFAULT 5,
            confidence REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'active',
            retention_class TEXT NOT NULL DEFAULT 'durable'
                CHECK (retention_class IN ('durable', 'expirable', 'superseded')),
            source_kind TEXT NOT NULL,
            source_conversation_id TEXT,
            author_actor TEXT NOT NULL,
            supersedes_id INTEGER,
            superseded_by_id INTEGER,
            deleted_at TIMESTAMP,
            deleted_by_actor TEXT,
            deletion_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_user_id) REFERENCES users(id),
            FOREIGN KEY (supersedes_id) REFERENCES user_memories(id),
            FOREIGN KEY (superseded_by_id) REFERENCES user_memories(id)
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_memories_active_dedupe
        ON user_memories(subject_user_id, normalized_kind, normalized_content)
        WHERE status = 'active'
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_memories_active_retrieval
        ON user_memories(subject_user_id, status, importance DESC, updated_at DESC, id DESC)
    """)

    # --- Resource Referral Directory ---
    # Admin-curated directory of trusted real-world resources (lawyers, NGOs, UN bodies,
    # clinics, shelters, financial aid) that the agent can surface when a conversation
    # escalates from information to action. Retrieval is faceted on region + help-type,
    # not semantic similarity. See region_data.py for the ISO 3166 / UN M49 taxonomy.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT UNIQUE NOT NULL,
            name TEXT,
            resource_type TEXT,
            description TEXT,
            contact TEXT,
            languages TEXT,
            scope_level TEXT CHECK(scope_level IN ('country', 'subregion', 'region', 'global')),
            scope_code TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'ready', 'archived')),
            verified_at TIMESTAMP,
            vetted_by TEXT,
            source_note TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resources_scope ON resources(scope_level, scope_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status)")

    # Operator-extensible vocabulary of help types (seeded with a core set).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_types (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Many-to-many: which help types a resource provides (the facet we filter on).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_help_types (
            resource_id TEXT NOT NULL,
            help_type TEXT NOT NULL,
            PRIMARY KEY (resource_id, help_type),
            FOREIGN KEY (resource_id) REFERENCES resources(resource_id) ON DELETE CASCADE,
            FOREIGN KEY (help_type) REFERENCES help_types(key) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resource_help_types_type ON resource_help_types(help_type)")

    # Static ISO 3166 + UN M49 region map, seeded from region_data.py for SQL joins.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS country_regions (
            country_code TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            subregion_code TEXT,
            subregion_name TEXT,
            region_code TEXT,
            region_name TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_country_regions_name ON country_regions(country_name)")

    # --- Session Logs (Test & Feedback) ---
    # Captured chat transcripts for admin review / refinement. `source` keeps this
    # general so we are not boxed into admin-only testing: 'admin_test' = an admin
    # chatting as a user persona; 'user' = a real user's session logged for review.
    # Transcript content is NIP-04 encrypted to the admin pubkey AT REST — the file
    # at transcript_path holds only ciphertext, and transcript_ephemeral_pubkey is
    # the ephemeral pubkey the admin needs to decrypt client-side via NIP-07. The
    # control plane can never read it back. See encryption.encrypt_for_admin.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL DEFAULT 'admin_test'
                CHECK(source IN ('admin_test', 'user')),
            title TEXT,
            subject_user_id INTEGER,
            user_type_id INTEGER,
            sage_session_id TEXT,
            transcript_path TEXT,
            transcript_ephemeral_pubkey TEXT,
            encrypted_to_pubkey TEXT,
            turn_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'completed', 'archived')),
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (subject_user_id) REFERENCES users(id),
            FOREIGN KEY (user_type_id) REFERENCES user_types(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_logs_status ON session_logs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_logs_source ON session_logs(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_logs_user_type ON session_logs(user_type_id)")

    # Per-turn feedback on a logged session. The rating stays plaintext so it can
    # be queried/aggregated; the optional qualitative comment is NIP-04 encrypted
    # to the admin pubkey because it may quote sensitive transcript content.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_log_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id TEXT NOT NULL,
            turn_index INTEGER NOT NULL,
            rating TEXT NOT NULL CHECK(rating IN ('up', 'down')),
            comment_ciphertext TEXT,
            comment_ephemeral_pubkey TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(log_id, turn_index),
            FOREIGN KEY (log_id) REFERENCES session_logs(log_id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_log_feedback_log ON session_log_feedback(log_id)")

    conn.commit()
    logger.info("SQLite schema initialized")

    # Run migrations for existing tables (must run BEFORE creating indexes on new columns)
    _migrate_add_approved_column()
    _migrate_add_encryption_columns()  # This adds email_blind_index column AND creates its index
    _migrate_add_field_metadata_columns()  # Add placeholder and options columns
    _migrate_add_encryption_enabled_column()  # Add encryption_enabled column for optional field encryption
    _migrate_add_include_in_chat_column()  # Add include_in_chat column for AI chat context
    _migrate_add_user_type_icon_column()  # Add icon column to user_types table
    _migrate_encrypt_deployment_config_secrets()  # Encrypt plaintext deployment secrets at rest
    _migrate_add_config_audit_hash_columns()  # Add tamper-evident hash chain to config audit log
    _migrate_add_admin_session_nonce_column()  # Add admin session nonce for server-side session revocation
    _migrate_enforce_single_admin()  # Enforce the single-admin product invariant at the DB layer
    _migrate_deletion_tombstones_status_check()  # Enforce lifecycle tombstone status values
    _migrate_add_user_memory_retention_class()  # Classify User Memory for conservative retention

    # Initialize ingest job tables
    from ingest_db import init_ingest_schema
    init_ingest_schema()

    # Seed default Agent Settings values
    _seed_default_ai_config()
    seed_default_settings()

    # Seed resource-directory infrastructure (region map + core help-type vocabulary).
    # Example resources are seeded separately (demo data) in seed.py.
    seed_country_regions()
    seed_help_types()
    _migrate_resource_help_types_help_type_fk()  # Enforce resource help-type vocabulary membership


def _migrate_resource_help_types_help_type_fk() -> None:
    """Rebuild resource_help_types with a help_types foreign key when needed."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_key_list(resource_help_types)")
    foreign_keys = cursor.fetchall()
    if any(row["table"] == "help_types" for row in foreign_keys):
        cursor.close()
        return

    cursor.execute("DROP TABLE IF EXISTS resource_help_types_new")
    cursor.execute("""
        CREATE TABLE resource_help_types_new (
            resource_id TEXT NOT NULL,
            help_type TEXT NOT NULL,
            PRIMARY KEY (resource_id, help_type),
            FOREIGN KEY (resource_id) REFERENCES resources(resource_id) ON DELETE CASCADE,
            FOREIGN KEY (help_type) REFERENCES help_types(key) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO resource_help_types_new (resource_id, help_type)
        SELECT rht.resource_id, rht.help_type
        FROM resource_help_types rht
        JOIN resources r ON r.resource_id = rht.resource_id
        JOIN help_types ht ON ht.key = rht.help_type
    """)
    cursor.execute("DROP TABLE resource_help_types")
    cursor.execute("ALTER TABLE resource_help_types_new RENAME TO resource_help_types")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resource_help_types_type ON resource_help_types(help_type)")
    conn.commit()
    logger.info("Migration: Rebuilt resource_help_types with help_types foreign key")
    cursor.close()


def _migrate_add_approved_column() -> None:
    """Add approved column to users table if it doesn't exist (for existing deployments)"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'approved' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 1")
        conn.commit()
        logger.info("Migration: Added 'approved' column to users table")

    cursor.close()


def _migrate_add_encryption_columns() -> None:
    """Add encryption columns to users and user_field_values tables if they don't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check users table columns
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]

    # Add encryption columns to users table
    user_encryption_columns = [
        ("encrypted_email", "TEXT"),
        ("ephemeral_pubkey_email", "TEXT"),
        ("email_blind_index", "TEXT"),
        ("encrypted_name", "TEXT"),
        ("ephemeral_pubkey_name", "TEXT"),
    ]

    for col_name, col_type in user_encryption_columns:
        if col_name not in user_columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            logger.info(f"Migration: Added '{col_name}' column to users table")

    # Check user_field_values table columns
    cursor.execute("PRAGMA table_info(user_field_values)")
    field_columns = [row[1] for row in cursor.fetchall()]

    # Add encryption columns to user_field_values table
    field_encryption_columns = [
        ("encrypted_value", "TEXT"),
        ("ephemeral_pubkey", "TEXT"),
    ]

    for col_name, col_type in field_encryption_columns:
        if col_name not in field_columns:
            cursor.execute(f"ALTER TABLE user_field_values ADD COLUMN {col_name} {col_type}")
            logger.info(f"Migration: Added '{col_name}' column to user_field_values table")

    conn.commit()

    # Enforce unique blind index for email lookups
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_users_email_blind_index")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_blind_index ON users(email_blind_index)")
        conn.commit()
    except sqlite3.IntegrityError as e:
        logger.error(f"Migration: Duplicate email_blind_index values detected: {e}")
        raise

    cursor.close()


def _migrate_add_field_metadata_columns() -> None:
    """Add placeholder and options columns to user_field_definitions if they don't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(user_field_definitions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'placeholder' not in columns:
        cursor.execute("ALTER TABLE user_field_definitions ADD COLUMN placeholder TEXT")
        logger.info("Migration: Added 'placeholder' column to user_field_definitions table")

    if 'options' not in columns:
        cursor.execute("ALTER TABLE user_field_definitions ADD COLUMN options TEXT")  # JSON array
        logger.info("Migration: Added 'options' column to user_field_definitions table")

    conn.commit()
    cursor.close()


def _migrate_add_encryption_enabled_column() -> None:
    """Add encryption_enabled column to user_field_definitions if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(user_field_definitions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'encryption_enabled' not in columns:
        # Add column with secure default (1 = encrypted)
        cursor.execute("ALTER TABLE user_field_definitions ADD COLUMN encryption_enabled INTEGER DEFAULT 1")
        logger.info("Migration: Added 'encryption_enabled' column to user_field_definitions table (default: encrypted)")

    # Always ensure index exists (idempotent via IF NOT EXISTS)
    # This runs after column is guaranteed to exist (either from CREATE TABLE or ALTER TABLE above)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_field_definitions_encryption ON user_field_definitions(encryption_enabled)")

    conn.commit()
    cursor.close()


def _migrate_add_include_in_chat_column() -> None:
    """Add include_in_chat column to user_field_definitions if it doesn't exist.

    This column controls whether a field's value should be included in AI chat context
    to personalize responses. Only unencrypted fields can be included (encrypted fields
    require admin's private key to decrypt, but chat runs in user context).
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(user_field_definitions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'include_in_chat' not in columns:
        # Add column with default 0 (not included in chat)
        cursor.execute("ALTER TABLE user_field_definitions ADD COLUMN include_in_chat INTEGER DEFAULT 0")
        logger.info("Migration: Added 'include_in_chat' column to user_field_definitions table (default: not included)")

    # Create index for efficient lookups of fields to include in chat
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_field_definitions_include_in_chat ON user_field_definitions(include_in_chat)")

    conn.commit()
    cursor.close()


def _migrate_add_user_type_icon_column() -> None:
    """Add icon column to user_types if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user_types)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'icon' not in columns:
        cursor.execute("ALTER TABLE user_types ADD COLUMN icon TEXT")
        logger.info("Migration: Added 'icon' column to user_types table")

    conn.commit()
    cursor.close()


def _migrate_add_admin_session_nonce_column() -> None:
    """Add session_nonce column to admins if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(admins)")
    columns = [row[1] for row in cursor.fetchall()]

    if "session_nonce" not in columns:
        cursor.execute("ALTER TABLE admins ADD COLUMN session_nonce INTEGER DEFAULT 0")
        logger.info("Migration: Added 'session_nonce' column to admins table (default: 0)")
        cursor.execute("UPDATE admins SET session_nonce = 0 WHERE session_nonce IS NULL")

    conn.commit()
    cursor.close()


def _migrate_enforce_single_admin() -> None:
    """Collapse legacy duplicate admins and prevent future direct inserts."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, pubkey FROM admins ORDER BY created_at, id")
    admins = cursor.fetchall()
    if len(admins) > 1:
        keep_id = admins[0]["id"]
        removed_pubkeys = [row["pubkey"] for row in admins[1:]]
        cursor.execute("DELETE FROM admins WHERE id != ?", (keep_id,))
        logger.warning(
            "Migration: Removed %s duplicate admin row(s) to enforce single-admin invariant: %s",
            len(removed_pubkeys),
            ", ".join(pubkey[:16] + "..." for pubkey in removed_pubkeys),
        )

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_admins_singleton_insert
        BEFORE INSERT ON admins
        WHEN (SELECT COUNT(*) FROM admins) >= 1
        BEGIN
            SELECT RAISE(ABORT, 'Only one admin per instance is allowed.');
        END
    """)

    conn.commit()
    cursor.close()


def _migrate_deletion_tombstones_status_check() -> None:
    """Rebuild deletion_tombstones if it lacks the status CHECK constraint."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'deletion_tombstones'"
    )
    row = cursor.fetchone()
    table_sql = row[0] if row else ""
    if "CHECK(status IN ('incomplete', 'completed'))" in table_sql:
        cursor.execute("""
            DELETE FROM deletion_tombstones
            WHERE status = 'incomplete'
              AND id NOT IN (
                  SELECT MAX(id)
                  FROM deletion_tombstones
                  WHERE status = 'incomplete'
                  GROUP BY conversation_id
              )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_deletion_tombstones_incomplete_conversation
            ON deletion_tombstones(conversation_id)
            WHERE status = 'incomplete'
        """)
        conn.commit()
        cursor.close()
        return

    cursor.execute("SELECT COUNT(*) FROM deletion_tombstones")
    count = cursor.fetchone()[0]
    cursor.execute("ALTER TABLE deletion_tombstones RENAME TO deletion_tombstones_old")
    cursor.execute("""
        CREATE TABLE deletion_tombstones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_data_class TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            former_subject_ref TEXT,
            status TEXT NOT NULL CHECK(status IN ('incomplete', 'completed')),
            source TEXT NOT NULL,
            workflow TEXT NOT NULL,
            deletion JSON NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO deletion_tombstones (
            id,
            lifecycle_data_class,
            conversation_id,
            former_subject_ref,
            status,
            source,
            workflow,
            deletion,
            retry_count,
            last_retry_at,
            created_at,
            updated_at
        )
        SELECT
            id,
            lifecycle_data_class,
            conversation_id,
            former_subject_ref,
            CASE WHEN status IN ('incomplete', 'completed') THEN status ELSE 'incomplete' END,
            source,
            workflow,
            deletion,
            retry_count,
            last_retry_at,
            created_at,
            updated_at
        FROM deletion_tombstones_old
    """)
    cursor.execute("DROP TABLE deletion_tombstones_old")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_deletion_tombstones_status
        ON deletion_tombstones(status, updated_at DESC)
    """)
    cursor.execute("""
        DELETE FROM deletion_tombstones
        WHERE status = 'incomplete'
          AND id NOT IN (
              SELECT MAX(id)
              FROM deletion_tombstones
              WHERE status = 'incomplete'
              GROUP BY conversation_id
          )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_deletion_tombstones_incomplete_conversation
        ON deletion_tombstones(conversation_id)
        WHERE status = 'incomplete'
    """)
    conn.commit()
    logger.info(
        "Migration: Rebuilt deletion_tombstones with status CHECK constraint (%s rows)",
        count,
    )
    cursor.close()


def _migrate_add_user_memory_retention_class() -> None:
    """Add conservative retention class metadata to existing User Memory records."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user_memories)")
    columns = [row[1] for row in cursor.fetchall()]
    if "retention_class" not in columns:
        cursor.execute(
            """
            ALTER TABLE user_memories
            ADD COLUMN retention_class TEXT NOT NULL DEFAULT 'durable'
            CHECK (retention_class IN ('durable', 'expirable', 'superseded'))
            """
        )
        cursor.execute(
            """
            UPDATE user_memories
            SET retention_class = 'superseded'
            WHERE status = 'superseded'
            """
        )
        cursor.execute(
            """
            UPDATE user_memories
            SET retention_class = 'expirable'
            WHERE source_kind = 'ambient'
              AND status != 'superseded'
              AND retention_class = 'durable'
            """
        )
        conn.commit()
        logger.info("Migration: Added 'retention_class' column to user_memories table")

    cursor.close()


def _migrate_encrypt_deployment_config_secrets() -> None:
    """Encrypt existing plaintext deployment_config secrets in place."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, key, value
        FROM deployment_config
        WHERE is_secret = 1
          AND value IS NOT NULL
          AND value != ''
    """)
    rows = cursor.fetchall()

    migrated = 0
    failed = 0
    for row in rows:
        raw_value = row["value"]
        try:
            if _is_deployment_secret_encrypted(raw_value):
                _decrypt_deployment_secret_value(raw_value)
                continue
            else:
                encrypted_value = _encrypt_deployment_secret_value(raw_value)
        except Exception as exc:
            failed += 1
            logger.error(
                "Migration: Failed to encrypt deployment_config secret key='%s' id=%s: %s",
                row["key"],
                row["id"],
                exc,
            )
            break
        cursor.execute(
            """
            UPDATE deployment_config
            SET value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (encrypted_value, row["id"]),
        )
        migrated += cursor.rowcount

    if failed > 0:
        conn.rollback()
        cursor.close()
        raise RuntimeError(
            f"Migration aborted: {failed} deployment_config secret(s) failed to encrypt. "
            "No changes committed — all secrets remain in their prior state."
        )

    conn.commit()
    cursor.close()

    if migrated > 0:
        logger.info(f"Migration: Encrypted {migrated} deployment_config secret value(s) at rest")


def _audit_hash_payload(
    prev_hash: str,
    table_name: str,
    config_key: str,
    old_value: str | None,
    new_value: str | None,
    changed_by: str,
    changed_at: str,
) -> str:
    """Build deterministic payload for audit hash chain."""
    parts = [
        prev_hash,
        table_name,
        config_key,
        old_value or "",
        new_value or "",
        changed_by,
        changed_at,
    ]
    return "|".join(parts)


def _insert_config_audit_log(
    cursor: sqlite3.Cursor,
    table_name: str,
    config_key: str,
    old_value: str | None,
    new_value: str | None,
    changed_by: str,
) -> dict:
    """
    Insert tamper-evident audit event with hash-chain linkage.

    Callers must ensure the cursor is inside a serialized transaction
    (e.g. BEGIN IMMEDIATE) so that the SELECT for prev_hash and the
    subsequent INSERT execute atomically.  Without this, concurrent
    writers could read the same prev_hash and fork the chain.
    """
    changed_at = datetime.utcnow().isoformat()

    cursor.execute("SELECT entry_hash FROM config_audit_log ORDER BY id DESC LIMIT 1")
    prev_row = cursor.fetchone()
    prev_hash = prev_row["entry_hash"] if prev_row and prev_row["entry_hash"] else ""

    payload = _audit_hash_payload(prev_hash, table_name, config_key, old_value, new_value, changed_by, changed_at)
    entry_hash = _compute_audit_entry_hash(payload)

    cursor.execute(
        """
        INSERT INTO config_audit_log (
            table_name, config_key, old_value, new_value, changed_by, changed_at, prev_hash, entry_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (table_name, config_key, old_value, new_value, changed_by, changed_at, prev_hash, entry_hash),
    )
    return {"id": int(cursor.lastrowid), "entry_hash": entry_hash}


def log_config_audit_event(
    table_name: str,
    config_key: str,
    old_value: str | None,
    new_value: str | None,
    changed_by: str,
) -> dict:
    """
    Public helper for writing tamper-evident config audit events.

    Uses get_write_cursor() (BEGIN IMMEDIATE) to acquire a write lock
    before reading the previous hash, preventing concurrent inserts
    from forking the hash chain.
    """
    with get_write_cursor() as cursor:
        return _insert_config_audit_log(cursor, table_name, config_key, old_value, new_value, changed_by)


def create_retention_run_record(
    *,
    trigger: str,
    actor: str,
    status: str,
    policy_snapshot: dict,
    counts: dict,
    results: list[dict],
    tombstone_refs: list[dict],
    audit_log_id: int | None,
    audit_entry_hash: str | None,
    started_at: str,
    finished_at: str,
) -> dict:
    if trigger not in {"manual", "machine"}:
        raise ValueError("Unsupported Retention Run trigger")
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO retention_run_records (
                trigger,
                actor,
                status,
                policy_snapshot,
                counts,
                results,
                tombstone_refs,
                audit_log_id,
                audit_entry_hash,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trigger,
                actor,
                status,
                _json_dumps_for_lifecycle(policy_snapshot),
                _json_dumps_for_lifecycle(counts),
                _json_dumps_for_lifecycle(results),
                _json_dumps_for_lifecycle(tombstone_refs),
                audit_log_id,
                audit_entry_hash,
                started_at,
                finished_at,
            ),
        )
        record_id = int(cursor.lastrowid)
    record = get_retention_run_record(record_id)
    if record is None:
        raise RuntimeError("Created Retention Run Record could not be loaded")
    return record


def _retention_run_record_from_row(row: sqlite3.Row) -> dict:
    record = dict(row)
    for key in ("policy_snapshot", "counts", "results", "tombstone_refs"):
        try:
            record[key] = json.loads(record[key])
        except (TypeError, json.JSONDecodeError):
            record[key] = {} if key in {"policy_snapshot", "counts"} else []
    return record


def get_retention_run_record(record_id: int) -> dict | None:
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM retention_run_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        return _retention_run_record_from_row(row) if row else None


def list_retention_run_records(limit: int = 100, trigger: str | None = None) -> list[dict]:
    bounded_limit = max(1, min(int(limit), 500))
    with get_cursor() as cursor:
        if trigger is not None:
            cursor.execute(
                """
                SELECT *
                FROM retention_run_records
                WHERE trigger = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (trigger, bounded_limit),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM retention_run_records
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            )
        return [_retention_run_record_from_row(row) for row in cursor.fetchall()]


def create_deletion_tombstone(
    *,
    lifecycle_data_class: str,
    conversation_id: str,
    former_subject_ref: str | None,
    status: str,
    source: str,
    workflow: str,
    deletion: dict,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    serialized_deletion = _json_dumps_for_lifecycle(deletion)
    with get_write_cursor() as cursor:
        cursor.execute(
            """
            INSERT OR IGNORE INTO deletion_tombstones (
                lifecycle_data_class,
                conversation_id,
                former_subject_ref,
                status,
                source,
                workflow,
                deletion,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lifecycle_data_class,
                conversation_id,
                former_subject_ref,
                status,
                source,
                workflow,
                serialized_deletion,
                now,
                now,
            ),
        )
        if cursor.rowcount:
            return int(cursor.lastrowid)
        cursor.execute(
            """
            SELECT id FROM deletion_tombstones
            WHERE conversation_id = ? AND status = 'incomplete'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create or find deletion tombstone")
        return int(row["id"])


def list_deletion_tombstones(*, status: str | None = None, limit: int = 100) -> list[dict]:
    with get_cursor() as cursor:
        if status:
            cursor.execute(
                """
                SELECT * FROM deletion_tombstones
                WHERE status = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM deletion_tombstones
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
    tombstones = []
    for row in rows:
        item = dict(row)
        item["deletion"] = json.loads(item["deletion"])
        tombstones.append(item)
    return tombstones


def has_incomplete_deletion_tombstone_for_conversation(conversation_id: str) -> bool:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM deletion_tombstones
            WHERE conversation_id = ? AND status = 'incomplete'
            LIMIT 1
            """,
            (conversation_id,),
        )
        return cursor.fetchone() is not None


def summarize_deletion_tombstones() -> dict:
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT lifecycle_data_class, status, COUNT(*) AS count
            FROM deletion_tombstones
            GROUP BY lifecycle_data_class, status
            """
        )
        rows = cursor.fetchall()

    summary = {
        "total": 0,
        "incomplete": 0,
        "completed": 0,
        "by_class": {},
    }
    for row in rows:
        lifecycle_data_class = row["lifecycle_data_class"]
        status = row["status"]
        count = int(row["count"])
        summary["total"] += count
        if status in ("incomplete", "completed"):
            summary[status] += count
        class_counts = summary["by_class"].setdefault(
            lifecycle_data_class,
            {"total": 0, "incomplete": 0, "completed": 0},
        )
        class_counts["total"] += count
        if status in ("incomplete", "completed"):
            class_counts[status] += count
    return summary


def get_deletion_tombstone(tombstone_id: int) -> dict | None:
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM deletion_tombstones WHERE id = ?", (tombstone_id,))
        row = cursor.fetchone()
    if not row:
        return None
    item = dict(row)
    item["deletion"] = json.loads(item["deletion"])
    return item


def update_deletion_tombstone_after_retry(
    tombstone_id: int,
    *,
    status: str,
    deletion: dict,
) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()
    serialized_deletion = _json_dumps_for_lifecycle(deletion)
    with get_write_cursor() as cursor:
        cursor.execute(
            """
            UPDATE deletion_tombstones
            SET status = ?,
                deletion = ?,
                retry_count = retry_count + 1,
                last_retry_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, serialized_deletion, now, now, tombstone_id),
        )
    return get_deletion_tombstone(tombstone_id)


def _migrate_add_config_audit_hash_columns() -> None:
    """Add hash-chain columns to config_audit_log and backfill existing rows."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(config_audit_log)")
    columns = [row[1] for row in cursor.fetchall()]

    if "prev_hash" not in columns:
        cursor.execute("ALTER TABLE config_audit_log ADD COLUMN prev_hash TEXT")
        logger.info("Migration: Added 'prev_hash' column to config_audit_log")

    if "entry_hash" not in columns:
        cursor.execute("ALTER TABLE config_audit_log ADD COLUMN entry_hash TEXT")
        logger.info("Migration: Added 'entry_hash' column to config_audit_log")

    # Backfill/repair hash chain deterministically across full history.
    cursor.execute("""
        SELECT id, table_name, config_key, old_value, new_value, changed_by, changed_at
        FROM config_audit_log
        ORDER BY id
    """)
    rows = cursor.fetchall()

    prev_hash = ""
    for row in rows:
        changed_at = row["changed_at"] or datetime.utcnow().isoformat()
        payload = _audit_hash_payload(
            prev_hash=prev_hash,
            table_name=row["table_name"],
            config_key=row["config_key"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            changed_by=row["changed_by"],
            changed_at=changed_at,
        )
        entry_hash = _compute_audit_entry_hash(payload)
        cursor.execute(
            """
            UPDATE config_audit_log
            SET changed_at = ?, prev_hash = ?, entry_hash = ?
            WHERE id = ?
            """,
            (changed_at, prev_hash, entry_hash, row["id"]),
        )
        prev_hash = entry_hash

    conn.commit()
    cursor.close()


def seed_default_settings():
    """Seed default instance settings if not present"""
    defaults = {
        "instance_name": "Enclave",
        "primary_color": "#3B82F6",
        "description": "A privacy-first RAG knowledge base",
        "logo_url": "",
        "favicon_url": "",
        "apple_touch_icon_url": "",
        "icon": "Sparkles",
        "assistant_icon": "Sparkles",
        "user_icon": "User",
        "assistant_name": "Enclave AI",
        "user_label": "You",
        "header_layout": "icon_name",
        "header_tagline": "",
        "chat_bubble_style": "soft",
        "chat_bubble_shadow": "true",
        "surface_style": "plain",
        "status_icon_set": "classic",
        "typography_preset": "modern",
        "default_theme": "system",
        "auto_approve_users": "true",  # true = auto-approve, false = require manual approval

        # User reachout (user-facing email submission; disabled by default)
        "reachout_enabled": "false",
        "reachout_mode": "support",  # feedback | help | support
        "reachout_title": "",
        "reachout_description": "",
        "reachout_button_label": "",
        "reachout_success_message": "",
        # Admin-only settings (still stored in instance_settings, but not exposed publicly)
        "reachout_to_email": "",
        "reachout_subject_prefix": "",
        "reachout_rate_limit_per_hour": "3",
        "reachout_rate_limit_per_day": "10",
        "reachout_include_ip": "false",  # Include masked client IP in reachout emails (GDPR: IP is personal data)
    }

    with get_cursor() as cursor:
        for key, value in defaults.items():
            cursor.execute("""
                INSERT OR IGNORE INTO instance_settings (key, value)
                VALUES (?, ?)
            """, (key, value))

    logger.info("Default instance settings seeded")


# Reserved instance_settings row holding the set of keys an operator has
# explicitly configured (vs. untouched seed defaults). Used by guided onboarding
# to tell "operator chose this value" from "this is still the default placeholder"
# even when the chosen value happens to equal the default.
ONBOARDING_CONFIGURED_KEYS_SETTING = "onboarding_configured_keys"


def get_onboarding_configured_keys() -> set[str]:
    """Return the set of instance-settings keys the operator has explicitly set."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT value FROM instance_settings WHERE key = ?",
            (ONBOARDING_CONFIGURED_KEYS_SETTING,),
        )
        row = cursor.fetchone()
    if not row or not row["value"]:
        return set()
    try:
        parsed = json.loads(row["value"])
        return set(parsed) if isinstance(parsed, list) else set()
    except (json.JSONDecodeError, TypeError):
        return set()


def mark_onboarding_configured_keys(keys) -> None:
    """Record that the operator explicitly set these instance-settings keys."""
    incoming = {str(k) for k in keys if k and str(k) != ONBOARDING_CONFIGURED_KEYS_SETTING}
    if not incoming:
        return
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT value FROM instance_settings WHERE key = ?",
            (ONBOARDING_CONFIGURED_KEYS_SETTING,),
        )
        row = cursor.fetchone()
        existing: set[str] = set()
        if row and row["value"]:
            try:
                parsed = json.loads(row["value"])
                existing = set(parsed) if isinstance(parsed, list) else set()
            except (json.JSONDecodeError, TypeError):
                existing = set()
        updated = existing | incoming
        cursor.execute(
            """
            INSERT INTO instance_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ONBOARDING_CONFIGURED_KEYS_SETTING, json.dumps(sorted(updated))),
        )


# --- Admin Operations ---

def add_admin(pubkey: str) -> int:
    """
    Add the single admin by pubkey. Enforces single admin constraint.
    Returns admin id if successful.
    
    Raises:
        ValueError: If an admin already exists
    """
    with get_cursor() as cursor:
        # Atomic INSERT that only succeeds if no admin exists
        cursor.execute("""
            INSERT INTO admins (pubkey) 
            SELECT ? WHERE NOT EXISTS (SELECT 1 FROM admins)
        """, (pubkey,))
        
        # Check if the insert succeeded
        if cursor.rowcount == 0:
            raise ValueError("Instance already has an admin. Only one admin per instance is allowed.")
        
        admin_id = cursor.lastrowid
        
        # Mark admin as initialized
        cursor.execute("""
            INSERT OR REPLACE INTO instance_state (key, value, updated_at)
            VALUES ('admin_initialized', 'true', CURRENT_TIMESTAMP)
        """)
        
        return admin_id


def get_admin_by_pubkey(pubkey: str) -> dict | None:
    """Get admin by pubkey"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM admins WHERE pubkey = ?", (pubkey,))
        row = cursor.fetchone()
        return dict(row) if row else None


def increment_admin_session_nonce(pubkey: str) -> int:
    """
    Increment and return the current session nonce for the given admin.
    Incrementing invalidates all previously issued admin session tokens.
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            UPDATE admins
            SET session_nonce = COALESCE(session_nonce, 0) + 1
            WHERE pubkey = ?
            RETURNING session_nonce
            """,
            (pubkey,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Admin not found")
        return int(row["session_nonce"])


def is_admin(pubkey: str) -> bool:
    """Check if pubkey is an admin"""
    return get_admin_by_pubkey(pubkey) is not None


def list_admins() -> list[dict]:
    """List all admins"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM admins ORDER BY created_at")
        return [dict(row) for row in cursor.fetchall()]


def remove_admin(pubkey: str) -> bool:
    """Remove admin by pubkey. Returns True if removed."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM admins WHERE pubkey = ?", (pubkey,))
        removed = cursor.rowcount > 0
        
        # Check if any admins remain after deletion
        if removed:
            cursor.execute("SELECT COUNT(*) FROM admins")
            remaining_admins = cursor.fetchone()[0]
            
            # If no admins remain, reset instance state
            if remaining_admins == 0:
                cursor.execute("""
                    INSERT OR REPLACE INTO instance_state (key, value, updated_at)
                    VALUES ('admin_initialized', 'false', CURRENT_TIMESTAMP)
                """)
                cursor.execute("""
                    INSERT OR REPLACE INTO instance_state (key, value, updated_at)
                    VALUES ('setup_complete', 'false', CURRENT_TIMESTAMP)
                """)
        
        return removed


# --- Instance Settings Operations ---

def get_setting(key: str) -> str | None:
    """Get a single setting value"""
    with get_cursor() as cursor:
        cursor.execute("SELECT value FROM instance_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def get_all_settings() -> dict:
    """Get all instance settings as a dict"""
    with get_cursor() as cursor:
        cursor.execute("SELECT key, value FROM instance_settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}


def update_setting(key: str, value: str):
    """Update or insert a setting"""
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO instance_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))


def update_setting_with_audit(key: str, value: str, *, changed_by: str) -> None:
    """Update an Instance setting and append a tamper-evident audit entry."""
    with get_write_cursor() as cursor:
        cursor.execute("SELECT value FROM instance_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        old_value = row["value"] if row else None
        cursor.execute("""
            INSERT INTO instance_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        if old_value != value:
            _insert_config_audit_log(
                cursor,
                table_name="instance_settings",
                config_key=key,
                old_value=old_value,
                new_value=value,
                changed_by=changed_by,
            )


def update_settings(settings: dict[str, object]) -> None:
    """Update multiple settings at once"""
    def _coerce_setting_value(value: object) -> str:
        # Instance settings are persisted as TEXT. Keep a consistent representation.
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value)
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    for key, value in settings.items():
        if value is None:
            continue
        update_setting(key, _coerce_setting_value(value))


def get_auto_approve_users() -> bool:
    """Get whether new users should be auto-approved"""
    setting = get_setting("auto_approve_users")
    return setting != "false"  # Default to true if not set or not "false"


# --- Instance State Operations ---

def get_instance_state(key: str) -> str | None:
    """Get instance state value by key"""
    with get_cursor() as cursor:
        cursor.execute("SELECT value FROM instance_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def set_instance_state(key: str, value: str) -> None:
    """Set instance state value"""
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT OR REPLACE INTO instance_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))


def is_instance_setup_complete() -> bool:
    """Check if instance setup is complete"""
    admin_initialized = get_instance_state('admin_initialized') == 'true'
    setup_complete = get_instance_state('setup_complete') == 'true'
    return admin_initialized and setup_complete


def mark_instance_setup_complete() -> None:
    """Mark instance setup as complete (called after admin authentication)"""
    set_instance_state('setup_complete', 'true')


def has_admin() -> bool:
    """Check if instance has an admin configured"""
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM admins")
        return cursor.fetchone()[0] > 0


def get_single_admin() -> dict | None:
    """Get the single admin for this instance"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM admins LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None


# --- User Type Operations ---

def create_user_type(
    name: str,
    description: str | None = None,
    icon: str | None = None,
    display_order: int = 0
) -> int:
    """Create a user type. Returns type id."""
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO user_types (name, description, icon, display_order)
            VALUES (?, ?, ?, ?)
        """, (name, description, icon, display_order))
        return cursor.lastrowid


def get_user_type(type_id: int) -> dict | None:
    """Get a user type by id"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_types WHERE id = ?", (type_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_type_by_name(name: str) -> dict | None:
    """Get a user type by name"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_types WHERE name = ?", (name,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_user_types() -> list[dict]:
    """List all user types ordered by display_order"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM user_types
            ORDER BY display_order, id
        """)
        return [dict(row) for row in cursor.fetchall()]


def update_user_type(
    type_id: int,
    name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    display_order: int | None = None
) -> bool:
    """Update a user type. Returns True if updated."""
    updates = []
    values = []

    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if description is not None:
        updates.append("description = ?")
        values.append(description)
    if icon is not None:
        updates.append("icon = ?")
        values.append(icon)
    if display_order is not None:
        updates.append("display_order = ?")
        values.append(display_order)

    if not updates:
        return False

    values.append(type_id)

    with get_cursor() as cursor:
        cursor.execute(
            f"UPDATE user_types SET {', '.join(updates)} WHERE id = ?",
            values
        )
        return cursor.rowcount > 0


def delete_user_type(type_id: int) -> bool:
    """Delete a user type. Returns True if deleted. Cascades to field definitions."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM user_types WHERE id = ?", (type_id,))
        return cursor.rowcount > 0


# --- User Field Definition Operations ---

def _parse_field_definition_row(row: sqlite3.Row | None) -> dict | None:
    """Convert a DB row to a field-definition dict with parsed JSON metadata."""
    if row is None:
        return None

    field = dict(row)
    raw_options = field.get("options")
    if raw_options is None or (isinstance(raw_options, str) and not raw_options.strip()):
        field["options"] = None
    else:
        try:
            parsed = json.loads(raw_options)
            field["options"] = parsed if isinstance(parsed, list) else None
        except (TypeError, json.JSONDecodeError):
            field["options"] = None
    return field


def create_field_definition(
    field_name: str,
    field_type: str,
    required: bool = False,
    display_order: int = 0,
    user_type_id: int | None = None,
    placeholder: str | None = None,
    options: list[str] | None = None,
    encryption_enabled: bool = True,
    include_in_chat: bool = False
) -> int:
    """Create a user field definition. Returns field id.
    user_type_id: None = global field (shown for all types)
    placeholder: Placeholder text for the field input
    options: List of options for select fields (stored as JSON)
    encryption_enabled: True = encrypt field values (secure default), False = store plaintext
    include_in_chat: True = include field value in AI chat context (only for unencrypted fields)
    """
    # Enforce data consistency: encrypted fields cannot be included in chat context
    if encryption_enabled:
        include_in_chat = False

    options_json = json.dumps(options) if options is not None else None
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO user_field_definitions (field_name, field_type, required, display_order, user_type_id, placeholder, options, encryption_enabled, include_in_chat)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (field_name, field_type, int(required), display_order, user_type_id, placeholder, options_json, int(encryption_enabled), int(include_in_chat)))
        return cursor.lastrowid


def get_field_definitions(user_type_id: int | None = None, include_global: bool = True) -> list[dict]:
    """Get field definitions, optionally filtered by type.

    Args:
        user_type_id: If provided, filter to this type's fields
        include_global: If True and user_type_id provided, also include global fields (user_type_id IS NULL)
    """
    with get_cursor() as cursor:
        if user_type_id is None:
            # Return all fields
            cursor.execute("""
                SELECT * FROM user_field_definitions
                ORDER BY display_order, id
            """)
        elif include_global:
            # Return global fields + type-specific fields
            cursor.execute("""
                SELECT * FROM user_field_definitions
                WHERE user_type_id IS NULL OR user_type_id = ?
                ORDER BY user_type_id NULLS FIRST, display_order, id
            """, (user_type_id,))
        else:
            # Return only type-specific fields
            cursor.execute("""
                SELECT * FROM user_field_definitions
                WHERE user_type_id = ?
                ORDER BY display_order, id
            """, (user_type_id,))

        results = []
        for row in cursor.fetchall():
            parsed = _parse_field_definition_row(row)
            if parsed:
                results.append(parsed)
        return results


def get_field_definition_by_name(field_name: str, user_type_id: int | None = None) -> dict | None:
    """Get a field definition by name, optionally scoped to a type"""
    with get_cursor() as cursor:
        if user_type_id is None:
            # Look for global field first
            cursor.execute(
                "SELECT * FROM user_field_definitions WHERE field_name = ? AND user_type_id IS NULL",
                (field_name,)
            )
        else:
            # Look for type-specific field first, then global
            cursor.execute(
                """SELECT * FROM user_field_definitions
                   WHERE field_name = ? AND (user_type_id = ? OR user_type_id IS NULL)
                   ORDER BY user_type_id DESC NULLS LAST LIMIT 1""",
                (field_name, user_type_id)
            )
        return _parse_field_definition_row(cursor.fetchone())


def get_field_definition_by_id(field_id: int) -> dict | None:
    """Get a field definition by id"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_field_definitions WHERE id = ?", (field_id,))
        return _parse_field_definition_row(cursor.fetchone())


def update_field_definition(
    field_id: int,
    field_name: str | None = None,
    field_type: str | None = None,
    required: bool | None = None,
    display_order: int | None = None,
    user_type_id: int | None = ...,  # Use ... as sentinel for "not provided"
    placeholder: str | None = ...,
    options: list[str] | None = ...,
    encryption_enabled: bool | None = None,
    include_in_chat: bool | None = None
) -> bool:
    """Update a field definition. Returns True if updated.

    WARNING: Changing encryption_enabled may require data migration for existing field values.
    """
    updates = []
    values = []

    if field_name is not None:
        updates.append("field_name = ?")
        values.append(field_name)
    if field_type is not None:
        updates.append("field_type = ?")
        values.append(field_type)
    if required is not None:
        updates.append("required = ?")
        values.append(int(required))
    if display_order is not None:
        updates.append("display_order = ?")
        values.append(display_order)
    if user_type_id is not ...:
        updates.append("user_type_id = ?")
        values.append(user_type_id)
    if placeholder is not ...:
        updates.append("placeholder = ?")
        values.append(placeholder)
    if options is not ...:
        updates.append("options = ?")
        values.append(json.dumps(options) if options is not None else None)
    if encryption_enabled is not None:
        updates.append("encryption_enabled = ?")
        values.append(int(encryption_enabled))

    # Determine effective encryption status (incoming value or stored value)
    effective_encryption = bool(encryption_enabled) if encryption_enabled is not None else False
    if encryption_enabled is None:
        existing_field = get_field_definition_by_id(field_id)
        if existing_field is not None:
            existing_encryption = existing_field.get("encryption_enabled")
            effective_encryption = existing_encryption is True or existing_encryption == 1

    # Handle include_in_chat based on effective encryption status
    # Encrypted fields must always have include_in_chat=0 for data consistency
    if effective_encryption:
        updates.append("include_in_chat = ?")
        values.append(0)
    elif include_in_chat is not None:
        # Non-encrypted fields can have include_in_chat set from parameter
        updates.append("include_in_chat = ?")
        values.append(int(include_in_chat))

    if not updates:
        return False

    values.append(field_id)

    with get_cursor() as cursor:
        cursor.execute(
            f"UPDATE user_field_definitions SET {', '.join(updates)} WHERE id = ?",
            values
        )
        return cursor.rowcount > 0


def delete_field_definition(field_id: int) -> bool:
    """Delete a field definition and all associated values. Returns True if deleted."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM user_field_definitions WHERE id = ?", (field_id,))
        return cursor.rowcount > 0


# --- User Operations ---

def create_user(
    pubkey: str | None = None,
    email: str | None = None,
    name: str | None = None,
    user_type_id: int | None = None
) -> int:
    """Create a user. Returns user id.
    Approval status is based on auto_approve_users instance setting.
    Email and name are encrypted using NIP-04 if an admin exists.
    """
    # Import here to avoid circular imports
    from encryption import encrypt_for_admin_required, compute_blind_index
    from nostr_keys import normalize_pubkey

    approved = 1 if get_auto_approve_users() else 0

    # Normalize pubkey if provided
    if pubkey:
        pubkey = normalize_pubkey(pubkey)

    # Encrypt email if provided (strip whitespace first)
    encrypted_email = None
    ephemeral_pubkey_email = None
    email_blind_index = None
    trimmed_email = email.strip() if email else None
    if trimmed_email:
        encrypted_email, ephemeral_pubkey_email = encrypt_for_admin_required(trimmed_email)
        # Blind index uses lowercased email for case-insensitive lookups (matches get_user_by_email)
        email_blind_index = compute_blind_index(trimmed_email.lower())

    # Encrypt name if provided (strip whitespace first)
    encrypted_name = None
    ephemeral_pubkey_name = None
    trimmed_name = name.strip() if name else None
    if trimmed_name:
        encrypted_name, ephemeral_pubkey_name = encrypt_for_admin_required(trimmed_name)

    with get_cursor() as cursor:
        cursor.execute(
            """INSERT INTO users (
                pubkey, email, name, user_type_id, approved,
                encrypted_email, ephemeral_pubkey_email, email_blind_index,
                encrypted_name, ephemeral_pubkey_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pubkey,
                None,  # Never store plaintext email
                None,  # Never store plaintext name
                user_type_id,
                approved,
                encrypted_email,
                ephemeral_pubkey_email,
                email_blind_index,
                encrypted_name,
                ephemeral_pubkey_name,
            )
        )
        return cursor.lastrowid


def update_user_type_id(user_id: int, user_type_id: int | None) -> bool:
    """Update a user's type selection. Returns True if updated."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET user_type_id = ? WHERE id = ?",
            (user_type_id, user_id)
        )
        return cursor.rowcount > 0


def update_user_approval(user_id: int, approved: bool) -> bool:
    """Update a user's approval/access state. Returns True if updated."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET approved = ? WHERE id = ?",
            (1 if approved else 0, user_id)
        )
        return cursor.rowcount > 0


def get_user(user_id: int) -> dict | None:
    """Get user by id with all field values.

    Returns encrypted fields with their ephemeral pubkeys for frontend decryption.
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return None

        user = dict(user_row)

        # Structure encrypted data for frontend decryption
        if user.get("encrypted_email"):
            user["email_encrypted"] = {
                "ciphertext": user["encrypted_email"],
                "ephemeral_pubkey": user["ephemeral_pubkey_email"]
            }
        if user.get("encrypted_name"):
            user["name_encrypted"] = {
                "ciphertext": user["encrypted_name"],
                "ephemeral_pubkey": user["ephemeral_pubkey_name"]
            }

        # Get field values with encryption info
        cursor.execute("""
            SELECT fd.field_name, ufv.value, ufv.encrypted_value, ufv.ephemeral_pubkey
            FROM user_field_values ufv
            JOIN user_field_definitions fd ON fd.id = ufv.field_id
            WHERE ufv.user_id = ?
        """, (user_id,))

        user["fields"] = {}
        user["fields_encrypted"] = {}
        for row in cursor.fetchall():
            field_name = row["field_name"]
            if row["encrypted_value"]:
                # Encrypted field - frontend will decrypt
                user["fields_encrypted"][field_name] = {
                    "ciphertext": row["encrypted_value"],
                    "ephemeral_pubkey": row["ephemeral_pubkey"]
                }
                user["fields"][field_name] = None  # Placeholder
            else:
                # Legacy unencrypted field
                user["fields"][field_name] = row["value"]

        # Get user type info if set
        if user.get("user_type_id"):
            user_type = get_user_type(user["user_type_id"])
            user["user_type"] = user_type
        else:
            user["user_type"] = None

        return user


def get_user_by_pubkey(pubkey: str) -> dict | None:
    """Get user by pubkey"""
    from nostr_keys import normalize_pubkey

    try:
        pubkey = normalize_pubkey(pubkey)
    except ValueError:
        return None

    with get_cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE pubkey = ?", (pubkey,))
        row = cursor.fetchone()
        if row:
            return get_user(row["id"])
        return None


def set_user_pubkey(user_id: int, pubkey: str) -> bool:
    """Assign/replace a user's Nostr pubkey. Returns True if updated."""
    from nostr_keys import normalize_pubkey

    normalized = normalize_pubkey(pubkey)
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET pubkey = ? WHERE id = ?",
            (normalized, user_id),
        )
        return cursor.rowcount > 0


def get_user_by_email(email: str) -> dict | None:
    """Get user by email.

    Uses blind index for encrypted emails.
    """
    from encryption import compute_blind_index

    # Normalize email: strip whitespace and lowercase
    normalized_email = email.strip().lower() if email else ""
    if not normalized_email:
        return None

    # Compute blind index for the normalized email
    blind_index = compute_blind_index(normalized_email)

    with get_cursor() as cursor:
        # Try blind index first (encrypted emails)
        cursor.execute(
            "SELECT id FROM users WHERE email_blind_index = ? ORDER BY id DESC LIMIT 1",
            (blind_index,)
        )
        row = cursor.fetchone()
        if row:
            return get_user(row["id"])

        return None


def list_users() -> list[dict]:
    """List all users with their field values"""
    with get_cursor() as cursor:
        cursor.execute("SELECT id FROM users ORDER BY created_at")
        return [get_user(row["id"]) for row in cursor.fetchall()]


def set_user_field(user_id: int, field_name: str, value: object, user_type_id: int | None = None):
    """Set a field value for a user.

    Values are encrypted using NIP-04 if the field definition has encryption_enabled=True
    and an admin exists. Otherwise, stored as plaintext.
    """
    from encryption import encrypt_for_admin_required, serialize_field_value

    field_def = get_field_definition_by_name(field_name, user_type_id)
    if not field_def:
        raise ValueError(f"Unknown field: {field_name}")

    # Serialize value to string
    serialized = serialize_field_value(value)

    # Check if encryption is enabled for this field
    if field_def.get("encryption_enabled", 1):  # Default to encrypted for backward compatibility
        # ENCRYPTED PATH - encrypt the value
        encrypted_value, ephemeral_pubkey = encrypt_for_admin_required(serialized)
        
        # Store encrypted - clear plaintext
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_field_values (user_id, field_id, value, encrypted_value, ephemeral_pubkey)
                VALUES (?, ?, NULL, ?, ?)
                ON CONFLICT(user_id, field_id) DO UPDATE SET
                    value = NULL,
                    encrypted_value = excluded.encrypted_value,
                    ephemeral_pubkey = excluded.ephemeral_pubkey
            """, (user_id, field_def["id"], encrypted_value, ephemeral_pubkey))
    else:
        # PLAINTEXT PATH - store value directly
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_field_values (user_id, field_id, value, encrypted_value, ephemeral_pubkey)
                VALUES (?, ?, ?, NULL, NULL)
                ON CONFLICT(user_id, field_id) DO UPDATE SET
                    value = excluded.value,
                    encrypted_value = NULL,
                    ephemeral_pubkey = NULL
            """, (user_id, field_def["id"], serialized))


def set_user_fields(user_id: int, fields: dict, user_type_id: int | None = None):
    """Set multiple field values for a user"""
    for field_name, value in fields.items():
        set_user_field(user_id, field_name, value, user_type_id)


def get_user_chat_context_values(user_id: int, user_type_id: int | None = None) -> dict[str, str]:
    """Get unencrypted field values for fields marked include_in_chat=1.

    Returns a dict of {field_name: value} for use in AI chat context.
    Only returns plaintext values (not encrypted_value) from fields that have:
    - encryption_enabled=0 (unencrypted)
    - include_in_chat=1 (marked for chat inclusion)

    Args:
        user_id: The user's ID
        user_type_id: If provided, also includes type-specific fields

    Returns:
        Dict mapping field names to their plaintext values
    """
    with get_cursor() as cursor:
        # Query joins field definitions with field values
        # Only gets unencrypted fields marked for chat inclusion
        if user_type_id is not None:
            # Include global fields (user_type_id IS NULL) and type-specific fields
            cursor.execute("""
                SELECT fd.field_name, ufv.value
                FROM user_field_values ufv
                JOIN user_field_definitions fd ON fd.id = ufv.field_id
                WHERE ufv.user_id = ?
                  AND fd.encryption_enabled = 0
                  AND fd.include_in_chat = 1
                  AND (fd.user_type_id IS NULL OR fd.user_type_id = ?)
                  AND ufv.value IS NOT NULL
                  AND ufv.value != ''
                ORDER BY fd.user_type_id IS NULL DESC
            """, (user_id, user_type_id))
        else:
            # Only global fields
            cursor.execute("""
                SELECT fd.field_name, ufv.value
                FROM user_field_values ufv
                JOIN user_field_definitions fd ON fd.id = ufv.field_id
                WHERE ufv.user_id = ?
                  AND fd.encryption_enabled = 0
                  AND fd.include_in_chat = 1
                  AND fd.user_type_id IS NULL
                  AND ufv.value IS NOT NULL
                  AND ufv.value != ''
            """, (user_id,))

        return {row["field_name"]: row["value"] for row in cursor.fetchall()}


def _normalize_user_memory_text(value: str) -> str:
    """Normalize User Memory text for obvious duplicate detection."""
    return re.sub(r"\s+", " ", value.strip().lower())


def _validate_user_memory_scores(importance: int, confidence: float) -> tuple[int, float]:
    try:
        normalized_importance = int(importance)
    except (TypeError, ValueError) as exc:
        raise ValueError("User Memory importance must be an integer") from exc
    try:
        normalized_confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("User Memory confidence must be a number") from exc
    if not 0 <= normalized_importance <= 10:
        raise ValueError("User Memory importance must be between 0 and 10")
    if not 0.0 <= normalized_confidence <= 1.0:
        raise ValueError("User Memory confidence must be between 0.0 and 1.0")
    return normalized_importance, normalized_confidence


def _require_non_empty_user_memory_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"User Memory {field_name} is required")
    return value.strip()


def _user_memory_retention_class_for_source(source_kind: str) -> str:
    if source_kind.strip().lower() == "ambient":
        return "expirable"
    return "durable"


def _user_memory_row_to_dict(row: sqlite3.Row) -> dict:
    memory = dict(row)
    memory["confidence"] = float(memory["confidence"])
    return memory


def create_user_memory(
    *,
    subject_user_id: int,
    kind: str,
    content: str,
    importance: int = 5,
    confidence: float = 1.0,
    source_kind: str,
    source_conversation_id: str | None = None,
    author_actor: str,
    retention_class: str | None = None,
) -> int:
    """Create active Sage-owned User Memory, skipping obvious active duplicates."""
    kind = _require_non_empty_user_memory_text(kind, "kind")
    content = _require_non_empty_user_memory_text(content, "content")
    normalized_kind = _normalize_user_memory_text(kind)
    normalized_content = _normalize_user_memory_text(content)
    source_kind = _require_non_empty_user_memory_text(source_kind, "source_kind")
    author_actor = _require_non_empty_user_memory_text(author_actor, "author_actor")
    normalized_importance, normalized_confidence = _validate_user_memory_scores(importance, confidence)
    normalized_retention_class = (
        retention_class.strip().lower()
        if isinstance(retention_class, str) and retention_class.strip()
        else _user_memory_retention_class_for_source(source_kind)
    )
    if normalized_retention_class not in {"durable", "expirable", "superseded"}:
        raise ValueError("User Memory retention_class must be durable, expirable, or superseded")
    if normalized_retention_class == "superseded":
        normalized_retention_class = _user_memory_retention_class_for_source(source_kind)

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT id, retention_class
            FROM user_memories
            WHERE subject_user_id = ?
              AND normalized_kind = ?
              AND normalized_content = ?
              AND status = 'active'
            LIMIT 1
        """, (subject_user_id, normalized_kind, normalized_content))
        existing = cursor.fetchone()
        if existing:
            if normalized_retention_class == "durable" and existing["retention_class"] != "durable":
                cursor.execute(
                    """
                    UPDATE user_memories
                    SET retention_class = 'durable',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (existing["id"],),
                )
            return int(existing["id"])

        cursor.execute("""
            INSERT OR IGNORE INTO user_memories (
                subject_user_id,
                kind,
                content,
                normalized_kind,
                normalized_content,
                importance,
                confidence,
                status,
                retention_class,
                source_kind,
                source_conversation_id,
                author_actor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            subject_user_id,
            kind.strip(),
            content.strip(),
            normalized_kind,
            normalized_content,
            normalized_importance,
            normalized_confidence,
            normalized_retention_class,
            source_kind,
            source_conversation_id,
            author_actor,
        ))
        if cursor.rowcount == 1:
            return int(cursor.lastrowid)

        cursor.execute("""
            SELECT id
            FROM user_memories
            WHERE subject_user_id = ?
              AND normalized_kind = ?
              AND normalized_content = ?
              AND status = 'active'
            LIMIT 1
        """, (subject_user_id, normalized_kind, normalized_content))
        existing = cursor.fetchone()
        if existing:
            return int(existing["id"])
        raise RuntimeError("User Memory insert was ignored but no active duplicate was found")


def list_active_user_memories(subject_user_id: int, limit: int = 20) -> list[dict]:
    """List active User Memory for one User, capped and ordered by importance then recency."""
    bounded_limit = max(0, min(int(limit), 100))
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT
                id,
                subject_user_id,
                kind,
                content,
                importance,
                confidence,
                status,
                retention_class,
                source_kind,
                source_conversation_id,
                author_actor,
                supersedes_id,
                superseded_by_id,
                deleted_at,
                deleted_by_actor,
                deletion_reason,
                created_at,
                updated_at
            FROM user_memories
            WHERE subject_user_id = ?
              AND status = 'active'
            ORDER BY importance DESC, updated_at DESC, id DESC
            LIMIT ?
        """, (subject_user_id, bounded_limit))
        return [_user_memory_row_to_dict(row) for row in cursor.fetchall()]


def get_user_memory(memory_id: int) -> dict | None:
    """Get one User Memory record, including inactive records."""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT
                id,
                subject_user_id,
                kind,
                content,
                importance,
                confidence,
                status,
                retention_class,
                source_kind,
                source_conversation_id,
                author_actor,
                supersedes_id,
                superseded_by_id,
                deleted_at,
                deleted_by_actor,
                deletion_reason,
                created_at,
                updated_at
            FROM user_memories
            WHERE id = ?
        """, (memory_id,))
        row = cursor.fetchone()
        return _user_memory_row_to_dict(row) if row else None


def soft_delete_user_memory(
    memory_id: int,
    *,
    deleted_by_actor: str,
    deletion_reason: str | None = None,
) -> bool:
    """Soft-delete a User Memory record without destroying its audit metadata."""
    if not deleted_by_actor.strip():
        raise ValueError("deleted_by_actor is required")

    with get_cursor() as cursor:
        cursor.execute("""
            UPDATE user_memories
            SET status = 'deleted',
                deleted_at = CURRENT_TIMESTAMP,
                deleted_by_actor = ?,
                deletion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status != 'deleted'
        """, (deleted_by_actor.strip(), deletion_reason, memory_id))
        return cursor.rowcount > 0


def supersede_user_memory(
    memory_id: int,
    *,
    content: str,
    importance: int = 5,
    confidence: float = 1.0,
    source_kind: str,
    source_conversation_id: str | None = None,
    author_actor: str,
) -> int:
    """Create a replacement User Memory and mark the original as superseded."""
    content = _require_non_empty_user_memory_text(content, "content")
    normalized_content = _normalize_user_memory_text(content)
    source_kind = _require_non_empty_user_memory_text(source_kind, "source_kind")
    author_actor = _require_non_empty_user_memory_text(author_actor, "author_actor")
    normalized_importance, normalized_confidence = _validate_user_memory_scores(importance, confidence)

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT subject_user_id, kind, normalized_kind
            FROM user_memories
            WHERE id = ?
              AND status = 'active'
        """, (memory_id,))
        old_memory = cursor.fetchone()
        if not old_memory:
            raise ValueError("Active User Memory record not found")

        cursor.execute("""
            UPDATE user_memories
            SET status = 'superseded',
                retention_class = 'superseded',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'active'
        """, (memory_id,))
        if cursor.rowcount == 0:
            raise ValueError("Active User Memory record was already superseded")

        cursor.execute("""
            INSERT INTO user_memories (
                subject_user_id,
                kind,
                content,
                normalized_kind,
                normalized_content,
                importance,
                confidence,
                status,
                retention_class,
                source_kind,
                source_conversation_id,
                author_actor,
                supersedes_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
        """, (
            old_memory["subject_user_id"],
            old_memory["kind"],
            content.strip(),
            old_memory["normalized_kind"],
            normalized_content,
            normalized_importance,
            normalized_confidence,
            _user_memory_retention_class_for_source(source_kind),
            source_kind,
            source_conversation_id,
            author_actor,
            memory_id,
        ))
        new_id = int(cursor.lastrowid)

        cursor.execute("""
            UPDATE user_memories
            SET superseded_by_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_id, memory_id))
        return new_id


def _purge_user_memories_for_subject_user_tx(cursor: sqlite3.Cursor, subject_user_id: int) -> int:
    cursor.execute("DELETE FROM user_memories WHERE subject_user_id = ?", (subject_user_id,))
    return cursor.rowcount


def purge_user_memories_for_subject_user(subject_user_id: int) -> int:
    """Permanently remove User Memory for a subject User after that User is deleted."""
    with get_cursor() as cursor:
        return _purge_user_memories_for_subject_user_tx(cursor, subject_user_id)


def delete_user_lifecycle(user_id: int) -> dict:
    """Delete a User Profile and associated User Memory with lifecycle counts."""
    with get_cursor() as cursor:
        purged_memories = _purge_user_memories_for_subject_user_tx(cursor, user_id)
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        user_deleted = cursor.rowcount > 0
        return {
            "user_deleted": user_deleted,
            "user_memories_deleted": purged_memories,
        }


def delete_user(user_id: int) -> bool:
    """Delete a user and all their field values. Returns True if deleted."""
    return bool(delete_user_lifecycle(user_id)["user_deleted"])


# --- Agent Settings Operations ---

def _seed_default_ai_config() -> None:
    """Seed default Agent Settings values if not present"""
    defaults = [
        # Prompt sections
        ("prompt_system", "You are a helpful, knowledgeable assistant for this private Enclave instance. In Admin Conversations, inspect available first-party context, choose reasonable defaults for unspecified configuration details, state important assumptions briefly, and present writes for Change Confirmation.", "string", "prompt_section", "Core system prompt"),
        ("prompt_tone", "Be helpful, concise, and professional. Acknowledge the user's question before answering.", "string", "prompt_section", "Voice and personality instructions"),
        ("prompt_rules", '["For ordinary step-by-step guidance, keep actions focused; for delegated Admin Conversation configuration tasks, group related settings into one executable change set for Change Confirmation.", "Never call prose-only bullets or recommendations a Change Confirmation; include exactly one valid JSON change set when proposing writes.", "NEVER invent sources, organization names, or contact information", "If asked about topics outside your knowledge base, acknowledge limitations"]', "json", "prompt_section", "Array of behavioral rules"),
        ("prompt_forbidden", '[]', "json", "prompt_section", "Topics to avoid or redirect"),
        ("prompt_greeting", "greeting_style", "string", "prompt_section", "Initial response style"),
        # Model Provider parameters
        ("temperature", "0.1", "number", "parameter", "Model Provider temperature (0.0-1.0)"),
        ("top_k", "8", "number", "parameter", "Retrieval count"),
        ("max_tokens", "2048", "number", "parameter", "Maximum generated response tokens"),
        # Session defaults
        ("web_search_default", "false", "boolean", "default", "Web search active by default for new sessions"),
        ("admin_trace_visibility", "detailed", "string", "default", "Conversation Trace visibility for Admin Conversations"),
        ("user_trace_visibility", "minimal", "string", "default", "Conversation Trace visibility for User Conversations"),
    ]

    with get_cursor() as cursor:
        for key, value, value_type, category, description in defaults:
            cursor.execute("""
                INSERT OR IGNORE INTO ai_config (key, value, value_type, category, description)
                VALUES (?, ?, ?, ?, ?)
            """, (key, value, value_type, category, description))

    logger.info("Default Agent Settings seeded")


def get_ai_config(key: str) -> dict | None:
    """Get a single Agent Settings value"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM ai_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_ai_config() -> list[dict]:
    """Get all Agent Settings values"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM ai_config ORDER BY category, key")
        return [dict(row) for row in cursor.fetchall()]


def get_ai_config_by_category(category: str) -> list[dict]:
    """Get Agent Settings values for a specific category"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM ai_config WHERE category = ? ORDER BY key", (category,))
        return [dict(row) for row in cursor.fetchall()]


def update_ai_config(key: str, value: str, changed_by: str) -> bool:
    """Update an Agent Settings value with audit logging"""
    with get_write_cursor() as cursor:
        # Get old value inside transaction to avoid TOCTOU race
        cursor.execute("SELECT value FROM ai_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        old_value = row["value"] if row else None

        cursor.execute("""
            UPDATE ai_config SET value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE key = ?
        """, (value, key))

        if cursor.rowcount > 0:
            # Log the change
            _insert_config_audit_log(cursor, "ai_config", key, old_value, value, changed_by)
            return True
        return False


# --- Agent Settings User-Type Override Operations ---

def get_ai_config_override(key: str, user_type_id: int) -> dict | None:
    """Get a single Agent Settings override for a user type"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM ai_config_user_type_overrides
            WHERE ai_config_key = ? AND user_type_id = ?
        """, (key, user_type_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_ai_config_overrides_by_type(user_type_id: int) -> list[dict]:
    """Get all Agent Settings overrides for a user type"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM ai_config_user_type_overrides
            WHERE user_type_id = ?
            ORDER BY ai_config_key
        """, (user_type_id,))
        return [dict(row) for row in cursor.fetchall()]


def upsert_ai_config_override(key: str, user_type_id: int, value: str, changed_by: str) -> bool:
    """Create or update an Agent Settings override for a user type"""
    with get_write_cursor() as cursor:
        # Get old value for audit log
        cursor.execute("""
            SELECT value FROM ai_config_user_type_overrides
            WHERE ai_config_key = ? AND user_type_id = ?
        """, (key, user_type_id))
        old_row = cursor.fetchone()
        old_value = old_row["value"] if old_row else None

        cursor.execute("""
            INSERT INTO ai_config_user_type_overrides (ai_config_key, user_type_id, value)
            VALUES (?, ?, ?)
            ON CONFLICT(ai_config_key, user_type_id) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, user_type_id, value))

        # Log the change (only if changed_by is provided)
        if changed_by:
            _insert_config_audit_log(
                cursor,
                "ai_config_user_type_overrides",
                f"{key}:type_{user_type_id}",
                old_value,
                value,
                changed_by,
            )

        return True


def delete_ai_config_override(key: str, user_type_id: int, changed_by: str = "") -> bool:
    """Delete an Agent Settings override (revert to global). Returns True if deleted."""
    with get_write_cursor() as cursor:
        # Get old value for audit log
        cursor.execute("""
            SELECT value FROM ai_config_user_type_overrides
            WHERE ai_config_key = ? AND user_type_id = ?
        """, (key, user_type_id))
        old_row = cursor.fetchone()
        old_value = old_row["value"] if old_row else None

        cursor.execute("""
            DELETE FROM ai_config_user_type_overrides
            WHERE ai_config_key = ? AND user_type_id = ?
        """, (key, user_type_id))

        deleted = cursor.rowcount > 0

        # Log the change if something was deleted
        if deleted and changed_by:
            _insert_config_audit_log(
                cursor,
                "ai_config_user_type_overrides",
                f"{key}:type_{user_type_id}",
                old_value,
                "(reverted to global)",
                changed_by,
            )

        return deleted


def get_effective_ai_config(user_type_id: int | None = None) -> list[dict]:
    """
    Get all Agent Settings values with inheritance applied.

    If user_type_id is provided, returns global config merged with user-type overrides.
    Override values replace global values for matching keys.
    Each item includes is_override flag and override_user_type_id if applicable.
    """
    # Start with global config
    all_config = get_all_ai_config()

    if user_type_id is None:
        # No user type, return global config with is_override=False
        for config in all_config:
            config["is_override"] = False
            config["override_user_type_id"] = None
        return all_config

    # Get overrides for this user type
    overrides = get_ai_config_overrides_by_type(user_type_id)
    overrides_by_key = {o["ai_config_key"]: o for o in overrides}

    # Merge: overrides win
    for config in all_config:
        key = config["key"]
        if key in overrides_by_key:
            override = overrides_by_key[key]
            config["value"] = override["value"]
            config["is_override"] = True
            config["override_user_type_id"] = user_type_id
            config["updated_at"] = override["updated_at"]
        else:
            config["is_override"] = False
            config["override_user_type_id"] = None

    return all_config


# --- Document Defaults Operations ---

def get_document_defaults(job_id: str) -> dict | None:
    """Get document defaults for a specific job"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM document_defaults WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_document_defaults() -> list[dict]:
    """List all document defaults"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT dd.*, ij.filename, ij.status, ij.total_chunks
            FROM document_defaults dd
            JOIN ingest_jobs ij ON dd.job_id = ij.job_id
            WHERE ij.is_current = 1
            ORDER BY dd.display_order, ij.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def upsert_document_defaults(
    job_id: str,
    is_available: bool = True,
    is_default_active: bool = True,
    display_order: int = 0,
    changed_by: str = ""
) -> bool:
    """Create or update document defaults"""
    with get_write_cursor() as cursor:
        # Get old value inside transaction to avoid TOCTOU race
        cursor.execute("SELECT is_available, is_default_active FROM document_defaults WHERE job_id = ?", (job_id,))
        old_row = cursor.fetchone()
        old_value = json.dumps({"is_available": bool(old_row["is_available"]), "is_default_active": bool(old_row["is_default_active"])}) if old_row else None

        cursor.execute("""
            INSERT INTO document_defaults (job_id, is_available, is_default_active, display_order)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                is_available = excluded.is_available,
                is_default_active = excluded.is_default_active,
                display_order = excluded.display_order,
                updated_at = CURRENT_TIMESTAMP
        """, (job_id, int(is_available), int(is_default_active), display_order))

        # Log the change
        new_value = json.dumps({"is_available": is_available, "is_default_active": is_default_active})
        if changed_by:
            _insert_config_audit_log(cursor, "document_defaults", job_id, old_value, new_value, changed_by)

        return True


def transfer_document_access(old_job_id: str, new_job_id: str, changed_by: str = "") -> None:
    """Copy global and user-type Document Access rows from one job to another."""
    with get_write_cursor() as cursor:
        cursor.execute("SELECT * FROM document_defaults WHERE job_id = ?", (old_job_id,))
        old_default = cursor.fetchone()
        if old_default:
            cursor.execute("SELECT * FROM document_defaults WHERE job_id = ?", (new_job_id,))
            existing_default = cursor.fetchone()
            old_value = json.dumps({
                "is_available": bool(existing_default["is_available"]),
                "is_default_active": bool(existing_default["is_default_active"]),
                "display_order": existing_default["display_order"],
            }) if existing_default else None

            cursor.execute("""
                INSERT INTO document_defaults (job_id, is_available, is_default_active, display_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    is_available = excluded.is_available,
                    is_default_active = excluded.is_default_active,
                    display_order = excluded.display_order,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                new_job_id,
                old_default["is_available"],
                old_default["is_default_active"],
                old_default["display_order"],
            ))
            if changed_by:
                new_value = json.dumps({
                    "is_available": bool(old_default["is_available"]),
                    "is_default_active": bool(old_default["is_default_active"]),
                })
                _insert_config_audit_log(cursor, "document_defaults", new_job_id, old_value, new_value, changed_by)

        cursor.execute("""
            SELECT * FROM document_defaults_user_type_overrides
            WHERE job_id = ?
        """, (old_job_id,))
        old_overrides = cursor.fetchall()
        for override in old_overrides:
            cursor.execute("""
                SELECT * FROM document_defaults_user_type_overrides
                WHERE job_id = ? AND user_type_id = ?
            """, (new_job_id, override["user_type_id"]))
            existing_override = cursor.fetchone()
            old_value = json.dumps({
                "is_available": bool(existing_override["is_available"]) if existing_override["is_available"] is not None else None,
                "is_default_active": bool(existing_override["is_default_active"]) if existing_override["is_default_active"] is not None else None,
            }) if existing_override else None

            cursor.execute("""
                INSERT INTO document_defaults_user_type_overrides (
                    job_id, user_type_id, is_available, is_default_active
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id, user_type_id) DO UPDATE SET
                    is_available = excluded.is_available,
                    is_default_active = excluded.is_default_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                new_job_id,
                override["user_type_id"],
                override["is_available"],
                override["is_default_active"],
            ))
            if changed_by:
                new_value = json.dumps({
                    "is_available": bool(override["is_available"]) if override["is_available"] is not None else None,
                    "is_default_active": bool(override["is_default_active"]) if override["is_default_active"] is not None else None,
                })
                _insert_config_audit_log(
                    cursor,
                    "document_defaults_user_type_overrides",
                    f"{new_job_id}:type_{override['user_type_id']}",
                    old_value,
                    new_value,
                    changed_by,
                )


def get_default_active_documents() -> list[str]:
    """Get list of job_ids that are default active"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT dd.job_id FROM document_defaults dd
            JOIN ingest_jobs ij ON dd.job_id = ij.job_id
            WHERE dd.is_available = 1
              AND dd.is_default_active = 1
              AND ij.is_current = 1
              AND ij.status IN ('completed', 'completed_with_errors')
            ORDER BY dd.display_order
        """)
        return [row["job_id"] for row in cursor.fetchall()]


def get_available_documents() -> list[str]:
    """Get list of job_ids that are available for use"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT dd.job_id FROM document_defaults dd
            JOIN ingest_jobs ij ON dd.job_id = ij.job_id
            WHERE dd.is_available = 1
              AND ij.is_current = 1
              AND ij.status IN ('completed', 'completed_with_errors')
            ORDER BY dd.display_order
        """)
        return [row["job_id"] for row in cursor.fetchall()]


# --- Document Defaults User-Type Override Operations ---

def get_document_defaults_override(job_id: str, user_type_id: int) -> dict | None:
    """Get document defaults override for a specific job and user type"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM document_defaults_user_type_overrides
            WHERE job_id = ? AND user_type_id = ?
        """, (job_id, user_type_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_document_defaults_overrides_by_type(user_type_id: int) -> list[dict]:
    """Get all document defaults overrides for a user type"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM document_defaults_user_type_overrides
            WHERE user_type_id = ?
            ORDER BY job_id
        """, (user_type_id,))
        return [dict(row) for row in cursor.fetchall()]


def upsert_document_defaults_override(
    job_id: str,
    user_type_id: int,
    is_available: bool | None = None,
    is_default_active: bool | None = None,
    changed_by: str = ""
) -> bool:
    """Create or update document defaults override for a user type"""
    with get_write_cursor() as cursor:
        # Get old value for audit log
        cursor.execute("""
            SELECT is_available, is_default_active FROM document_defaults_user_type_overrides
            WHERE job_id = ? AND user_type_id = ?
        """, (job_id, user_type_id))
        old_row = cursor.fetchone()
        old_value = json.dumps({
            "is_available": bool(old_row["is_available"]) if old_row and old_row["is_available"] is not None else None,
            "is_default_active": bool(old_row["is_default_active"]) if old_row and old_row["is_default_active"] is not None else None
        }) if old_row else None

        # Handle None values - only update fields that are provided
        if old_row:
            # Merge with existing values
            final_available = is_available if is_available is not None else (
                bool(old_row["is_available"]) if old_row["is_available"] is not None else None
            )
            final_active = is_default_active if is_default_active is not None else (
                bool(old_row["is_default_active"]) if old_row["is_default_active"] is not None else None
            )
        else:
            final_available = is_available
            final_active = is_default_active

        cursor.execute("""
            INSERT INTO document_defaults_user_type_overrides (job_id, user_type_id, is_available, is_default_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id, user_type_id) DO UPDATE SET
                is_available = excluded.is_available,
                is_default_active = excluded.is_default_active,
                updated_at = CURRENT_TIMESTAMP
        """, (
            job_id,
            user_type_id,
            int(final_available) if final_available is not None else None,
            int(final_active) if final_active is not None else None
        ))

        # Log the change
        new_value = json.dumps({"is_available": final_available, "is_default_active": final_active})
        if changed_by:
            _insert_config_audit_log(
                cursor,
                "document_defaults_user_type_overrides",
                f"{job_id}:type_{user_type_id}",
                old_value,
                new_value,
                changed_by,
            )

        return True


def delete_document_defaults_override(job_id: str, user_type_id: int, changed_by: str = "") -> bool:
    """Delete document defaults override (revert to global). Returns True if deleted."""
    with get_write_cursor() as cursor:
        # Get old value for audit log
        cursor.execute("""
            SELECT is_available, is_default_active FROM document_defaults_user_type_overrides
            WHERE job_id = ? AND user_type_id = ?
        """, (job_id, user_type_id))
        old_row = cursor.fetchone()
        old_value = json.dumps({
            "is_available": bool(old_row["is_available"]) if old_row and old_row["is_available"] is not None else None,
            "is_default_active": bool(old_row["is_default_active"]) if old_row and old_row["is_default_active"] is not None else None
        }) if old_row else None

        cursor.execute("""
            DELETE FROM document_defaults_user_type_overrides
            WHERE job_id = ? AND user_type_id = ?
        """, (job_id, user_type_id))

        deleted = cursor.rowcount > 0

        if deleted and changed_by:
            _insert_config_audit_log(
                cursor,
                "document_defaults_user_type_overrides",
                f"{job_id}:type_{user_type_id}",
                old_value,
                "(reverted to global)",
                changed_by,
            )

        return deleted


def get_effective_document_defaults(user_type_id: int | None = None) -> list[dict]:
    """
    Get all document defaults with inheritance applied.

    If user_type_id is provided, returns global defaults merged with user-type overrides.
    Override values replace global values for matching job_ids.
    Each item includes is_override flag if applicable.

    Also includes "orphan overrides" - documents with user-type overrides but no global entry.
    """
    # Get global defaults
    defaults = list_document_defaults()

    if user_type_id is None:
        # No user type, return global with is_override=False
        for doc in defaults:
            doc["is_override"] = False
            doc["override_user_type_id"] = None
        return defaults

    # Track which job_ids have global defaults
    global_job_ids = {doc["job_id"] for doc in defaults}

    # Get overrides for this user type
    overrides = get_document_defaults_overrides_by_type(user_type_id)
    overrides_by_job = {o["job_id"]: o for o in overrides}

    # Merge: overrides win for is_available and is_default_active
    for doc in defaults:
        job_id = doc["job_id"]
        if job_id in overrides_by_job:
            override = overrides_by_job[job_id]
            # Only override if the override has a non-None value
            if override["is_available"] is not None:
                doc["is_available"] = bool(override["is_available"])
            if override["is_default_active"] is not None:
                doc["is_default_active"] = bool(override["is_default_active"])
            doc["is_override"] = True
            doc["override_user_type_id"] = user_type_id
            doc["override_updated_at"] = override["updated_at"]
        else:
            doc["is_override"] = False
            doc["override_user_type_id"] = None

    # Add orphan overrides (overrides without global defaults)
    for job_id, override in overrides_by_job.items():
        if job_id not in global_job_ids:
            # Get job info from ingest_jobs
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT job_id, filename, status, total_chunks
                    FROM ingest_jobs
                    WHERE job_id = ?
                      AND is_current = 1
                      AND status IN ('completed', 'completed_with_errors')
                """, (job_id,))
                job_row = cursor.fetchone()
                if job_row:
                    defaults.append({
                        "id": None,  # No global default entry exists
                        "job_id": job_id,
                        "filename": job_row["filename"],
                        "status": job_row["status"],
                        "total_chunks": job_row["total_chunks"],
                        "is_available": bool(override["is_available"]) if override["is_available"] is not None else True,
                        "is_default_active": bool(override["is_default_active"]) if override["is_default_active"] is not None else True,
                        "display_order": 0,
                        "updated_at": override["updated_at"],
                        "is_override": True,
                        "override_user_type_id": user_type_id,
                        "override_updated_at": override["updated_at"],
                    })

    return defaults


def get_active_documents_for_user_type(user_type_id: int | None = None) -> list[str]:
    """
    Get list of job_ids that should be default active for a user type.

    Uses inheritance: user-type overrides take precedence over global defaults.
    """
    if user_type_id is None:
        return get_default_active_documents()

    effective = get_effective_document_defaults(user_type_id)
    return [doc["job_id"] for doc in effective if doc.get("is_available") and doc.get("is_default_active")]


def get_available_documents_for_user_type(user_type_id: int | None = None) -> list[str]:
    """
    Get list of job_ids that are available for a user type.

    Uses inheritance: user-type overrides take precedence over global defaults.
    """
    if user_type_id is None:
        return get_available_documents()

    effective = get_effective_document_defaults(user_type_id)
    return [doc["job_id"] for doc in effective if doc.get("is_available")]


# --- Deployment Configuration Operations ---

def get_deployment_config(key: str) -> dict | None:
    """Get a single deployment config value"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM deployment_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Mask secret values only when a value exists
            if result.get("is_secret") and result.get("value"):
                result["value"] = "********"
            return result
        return None


def get_all_deployment_config() -> list[dict]:
    """Get all deployment config values (secrets masked)"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM deployment_config ORDER BY category, key")
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get("is_secret") and result.get("value"):
                result["value"] = "********"
            results.append(result)
        return results


def get_deployment_config_by_category(category: str) -> list[dict]:
    """Get deployment config values for a specific category (secrets masked)"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM deployment_config WHERE category = ? ORDER BY key", (category,))
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get("is_secret") and result.get("value"):
                result["value"] = "********"
            results.append(result)
        return results


def update_deployment_config(key: str, value: str, changed_by: str) -> bool:
    """Update a deployment config value with audit logging"""
    # Get old value for audit log
    with get_write_cursor() as cursor:
        cursor.execute("SELECT value, is_secret FROM deployment_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return False
        old_value = "********" if row["is_secret"] else row["value"]
        value_to_store = _encrypt_deployment_secret_value(value) if row["is_secret"] and value else value

        cursor.execute("""
            UPDATE deployment_config SET value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE key = ?
        """, (value_to_store, key))

        if cursor.rowcount > 0:
            # Log the change (mask secrets in log too)
            new_value_logged = "********" if row["is_secret"] else value
            _insert_config_audit_log(
                cursor,
                "deployment_config",
                key,
                old_value,
                new_value_logged,
                changed_by,
            )
            return True
        return False


def upsert_deployment_config(
    key: str,
    value: str,
    is_secret: bool = False,
    requires_restart: bool = False,
    category: str = "general",
    description: str = "",
    changed_by: str = ""
) -> bool:
    """Create or update deployment config"""
    with get_write_cursor() as cursor:
        # Get old value inside transaction to avoid TOCTOU race
        cursor.execute("SELECT value, is_secret FROM deployment_config WHERE key = ?", (key,))
        old_row = cursor.fetchone()
        old_value = "********" if (old_row and old_row["is_secret"]) else (old_row["value"] if old_row else None)
        value_to_store = _encrypt_deployment_secret_value(value) if is_secret and value else value

        cursor.execute("""
            INSERT INTO deployment_config (key, value, is_secret, requires_restart, category, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                is_secret = excluded.is_secret,
                requires_restart = excluded.requires_restart,
                category = excluded.category,
                description = excluded.description,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value_to_store, int(is_secret), int(requires_restart), category, description))

        # Log the change
        if changed_by:
            new_value_logged = "********" if is_secret else value
            _insert_config_audit_log(
                cursor,
                "deployment_config",
                key,
                old_value,
                new_value_logged,
                changed_by,
            )

        return True


def get_restart_required_keys() -> list[str]:
    """Get list of config keys that require restart when changed"""
    with get_cursor() as cursor:
        cursor.execute("SELECT key FROM deployment_config WHERE requires_restart = 1")
        return [row["key"] for row in cursor.fetchall()]


def get_deployment_config_value(key: str) -> str | None:
    """Get the actual deployment config value (for internal system use only).

    WARNING: This returns unmasked secret values. Do not expose via API.
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT value, is_secret FROM deployment_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return None

        value = row["value"]
        if row["is_secret"] and value:
            try:
                return _decrypt_deployment_secret_value(value)
            except Exception as exc:
                logger.error(f"Failed to decrypt deployment secret for key '{key}': {exc}")
                return None

        return value


# --- Inference Verification Record Operations ---

INFERENCE_VERIFICATION_FRESHNESS_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_inference_time(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_inference_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _serialize_attestation_material(attestation_material: object | None) -> str | None:
    if attestation_material is None:
        return None
    if isinstance(attestation_material, str):
        raw = attestation_material
    else:
        raw = json.dumps(attestation_material, sort_keys=True, separators=(",", ":"), default=str)
    return _encrypt_deployment_secret_value(raw)


def _deserialize_attestation_material(encrypted: str | None) -> object | None:
    if not encrypted:
        return None
    raw = _decrypt_deployment_secret_value(encrypted)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _inference_record_from_row(row: sqlite3.Row, *, include_attestation: bool = False) -> dict:
    record = dict(row)
    encrypted = record.pop("encrypted_attestation_material", None)
    if include_attestation:
        record["attestation_material"] = _deserialize_attestation_material(encrypted)
    return record


def create_inference_verification_record(
    *,
    provider_identity: str,
    provider_endpoint: str,
    model_identifier: str,
    status: str,
    trigger: str,
    expected_claims_fingerprint: str,
    actual_claims_fingerprint: str | None,
    verifier_version: str,
    attestation_material: object | None = None,
    failure_category: str | None = None,
    failure_message: str | None = None,
    checked_at: datetime | str | None = None,
    expires_at: datetime | str | None = None,
) -> dict:
    """Create a historical Inference Verification Record."""
    normalized_status = status.strip().lower()
    if normalized_status not in {"success", "failed"}:
        raise ValueError("Inference Verification Record status must be success or failed")

    checked = checked_at if checked_at is not None else _utc_now()
    if expires_at is None and normalized_status == "success":
        checked_dt = _parse_inference_time(_format_inference_time(checked))
        expires_at = checked_dt + timedelta(hours=INFERENCE_VERIFICATION_FRESHNESS_HOURS)

    encrypted_attestation = _serialize_attestation_material(attestation_material)

    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO inference_verification_records (
                provider_identity,
                provider_endpoint,
                model_identifier,
                status,
                trigger,
                expected_claims_fingerprint,
                actual_claims_fingerprint,
                verifier_version,
                failure_category,
                failure_message,
                encrypted_attestation_material,
                checked_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            provider_identity,
            provider_endpoint,
            model_identifier,
            normalized_status,
            trigger,
            expected_claims_fingerprint,
            actual_claims_fingerprint,
            verifier_version,
            failure_category,
            failure_message,
            encrypted_attestation,
            _format_inference_time(checked),
            _format_inference_time(expires_at),
        ))
        record_id = cursor.lastrowid

    record = get_inference_verification_record(record_id)
    if record is None:
        raise RuntimeError("Created Inference Verification Record could not be loaded")
    return record


def get_inference_verification_record(record_id: int) -> dict | None:
    """Fetch one Inference Verification Record with decrypted full attestation material."""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM inference_verification_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        return _inference_record_from_row(row, include_attestation=True) if row else None


def list_inference_verification_records(limit: int = 100) -> list[dict]:
    """List normalized Inference Verification Record metadata without full attestation material."""
    bounded_limit = max(1, min(int(limit), 500))
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM inference_verification_records ORDER BY checked_at DESC, id DESC LIMIT ?",
            (bounded_limit,),
        )
        return [_inference_record_from_row(row, include_attestation=False) for row in cursor.fetchall()]


def get_current_inference_verification_status(
    *,
    provider_identity: str,
    provider_endpoint: str,
    model_identifier: str,
    expected_claims_fingerprint: str,
    now: datetime | str | None = None,
) -> dict:
    """Return the latest fresh successful matching verification record, if any."""
    now_dt = _parse_inference_time(_format_inference_time(now if now is not None else _utc_now()))
    now_iso = _format_inference_time(now_dt)
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT *
            FROM inference_verification_records
            WHERE provider_identity = ?
              AND provider_endpoint = ?
              AND model_identifier = ?
              AND expected_claims_fingerprint = ?
              AND status = 'success'
              AND checked_at <= ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY checked_at DESC, id DESC
            LIMIT 1
        """, (
            provider_identity,
            provider_endpoint,
            model_identifier,
            expected_claims_fingerprint,
            now_iso,
            now_iso,
        ))
        row = cursor.fetchone()

    if row:
        return {
            "status": "current",
            "checked_at": row["checked_at"],
            "expires_at": row["expires_at"],
            "record": _inference_record_from_row(row, include_attestation=False),
        }

    return {
        "status": "missing",
        "checked_at": None,
        "expires_at": None,
        "record": None,
    }


def get_current_inference_verification_status_for_config(
    *,
    expected_claims_fingerprint: str,
    now: datetime | str | None = None,
) -> dict:
    """Resolve current status for the configured Model Provider identity, endpoint, and model."""
    provider_identity = get_deployment_config_value("LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "sage")
    provider_endpoint = get_deployment_config_value("LLM_API_URL") or os.getenv("LLM_API_URL", "")
    model_identifier = get_deployment_config_value("LLM_MODEL") or os.getenv("LLM_MODEL", "")
    return get_current_inference_verification_status(
        provider_identity=provider_identity,
        provider_endpoint=provider_endpoint,
        model_identifier=model_identifier,
        expected_claims_fingerprint=expected_claims_fingerprint,
        now=now,
    )


# --- Audit Log Operations ---

def get_config_audit_log(limit: int | None = 100, table_name: str | None = None) -> list[dict]:
    """Get recent config audit log entries"""
    with get_cursor() as cursor:
        limit_clause = "" if limit is None else " LIMIT ?"
        if table_name:
            params: tuple[object, ...] = (table_name,) if limit is None else (table_name, limit)
            cursor.execute("""
                SELECT * FROM config_audit_log
                WHERE table_name = ?
                ORDER BY changed_at DESC
            """ + limit_clause, params)
        else:
            params = () if limit is None else (limit,)
            cursor.execute("""
                SELECT * FROM config_audit_log
                ORDER BY changed_at DESC
            """ + limit_clause, params)
        return [dict(row) for row in cursor.fetchall()]


def list_config_audit_log_compaction_candidates(cutoff_iso: str, limit: int = 1000) -> list[int]:
    """Return old non-lifecycle audit entries whose detail can be compacted."""
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM config_audit_log
            WHERE datetime(changed_at) <= datetime(?)
              AND table_name != 'data_deletion'
              AND (
                old_value IS NOT NULL
                OR new_value IS NOT NULL
              )
              AND COALESCE(old_value, '') NOT LIKE '%redacted_by_audit_log_retention%'
              AND COALESCE(new_value, '') NOT LIKE '%redacted_by_audit_log_retention%'
            ORDER BY id
            LIMIT ?
            """,
            (cutoff_iso, limit),
        )
        return [int(row["id"]) for row in cursor.fetchall()]


def compact_config_audit_log_before(cutoff_iso: str, *, changed_by: str) -> dict:
    """Redact old non-lifecycle audit detail while preserving the hash chain."""
    redacted_value = json.dumps({
        "redacted_by_audit_log_retention": True,
        "detail": "Original audit value compacted by evidence-preserving Audit Log Retention.",
    }, sort_keys=True)
    compacted_ids: list[int] = []
    with get_write_cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM config_audit_log
            WHERE datetime(changed_at) <= datetime(?)
              AND table_name != 'data_deletion'
              AND (
                old_value IS NOT NULL
                OR new_value IS NOT NULL
              )
              AND COALESCE(old_value, '') NOT LIKE '%redacted_by_audit_log_retention%'
              AND COALESCE(new_value, '') NOT LIKE '%redacted_by_audit_log_retention%'
            ORDER BY id
            LIMIT 1000
            """,
            (cutoff_iso,),
        )
        compacted_ids = [int(row["id"]) for row in cursor.fetchall()]
        if compacted_ids:
            placeholders = ",".join("?" for _ in compacted_ids)
            cursor.execute(
                f"""
                UPDATE config_audit_log
                SET old_value = CASE WHEN old_value IS NULL THEN NULL ELSE ? END,
                    new_value = CASE WHEN new_value IS NULL THEN NULL ELSE ? END
                WHERE id IN ({placeholders})
                """,
                (redacted_value, redacted_value, *compacted_ids),
            )

        cursor.execute(
            """
            SELECT id, table_name, config_key, old_value, new_value, changed_by, changed_at
            FROM config_audit_log
            ORDER BY id
            """
        )
        rows = cursor.fetchall()
        prev_hash = ""
        for row in rows:
            payload = _audit_hash_payload(
                prev_hash=prev_hash,
                table_name=row["table_name"],
                config_key=row["config_key"],
                old_value=row["old_value"],
                new_value=row["new_value"],
                changed_by=row["changed_by"],
                changed_at=row["changed_at"] or "",
            )
            entry_hash = _compute_audit_entry_hash(payload)
            cursor.execute(
                "UPDATE config_audit_log SET prev_hash = ?, entry_hash = ? WHERE id = ?",
                (prev_hash, entry_hash, row["id"]),
            )
            prev_hash = entry_hash

        _insert_config_audit_log(
            cursor,
            table_name="data_deletion",
            config_key=f"audit_log_retention:{datetime.utcnow().isoformat()}",
            old_value=None,
            new_value=json.dumps({
                "workflow": "audit_log_retention",
                "status": "succeeded",
                "compacted_entries": len(compacted_ids),
            }, sort_keys=True),
            changed_by=changed_by,
        )
    return {"compacted_entries": len(compacted_ids), "compacted_ids": compacted_ids}


def verify_config_audit_log_chain(table_name: str | None = None) -> dict:
    """
    Verify tamper-evident hash chain for config audit log.
    Integrity is validated across the full global chain. If `table_name` is set,
    `checked_entries` is scoped to that table while `total_entries` reflects the
    full chain size that was validated.

    Returns:
        {
          "valid": bool,
          "checked_entries": int,
          "first_invalid_id": int | None,
          "reason": str | None
        }
    """
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT id, table_name, config_key, old_value, new_value, changed_by, changed_at, prev_hash, entry_hash
            FROM config_audit_log
            ORDER BY id
        """)
        rows = cursor.fetchall()

    prev_hash = ""
    scoped_entries = 0
    for row in rows:
        in_scope = table_name is None or row["table_name"] == table_name
        if in_scope:
            scoped_entries += 1

        changed_at = row["changed_at"] or ""
        payload = _audit_hash_payload(
            prev_hash=prev_hash,
            table_name=row["table_name"],
            config_key=row["config_key"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            changed_by=row["changed_by"],
            changed_at=changed_at,
        )
        expected_entry_hash = _compute_audit_entry_hash(payload)

        if row["prev_hash"] != prev_hash:
            return {
                "valid": False,
                "checked_entries": scoped_entries if table_name is not None else len(rows),
                "total_entries": len(rows),
                "first_invalid_id": row["id"],
                "reason": "prev_hash mismatch",
            }

        if not hmac.compare_digest(row["entry_hash"] or "", expected_entry_hash):
            return {
                "valid": False,
                "checked_entries": scoped_entries if table_name is not None else len(rows),
                "total_entries": len(rows),
                "first_invalid_id": row["id"],
                "reason": "entry_hash mismatch",
            }

        prev_hash = row["entry_hash"] or ""

    return {
        "valid": True,
        "checked_entries": scoped_entries if table_name is not None else len(rows),
        "total_entries": len(rows),
        "first_invalid_id": None,
        "reason": None,
    }


# --- Resource Referral Directory ---

def _json_loads_or(default, raw):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _has_contact_method(contact: dict | None) -> bool:
    if not isinstance(contact, dict):
        return False
    return any(str(contact.get(k, "")).strip() for k in RESOURCE_CONTACT_KEYS)


def resource_missing_fields(merged: dict, help_types: list[str]) -> list[str]:
    """Return the list of REQUIRED fields still missing for a resource to be 'ready'."""
    missing: list[str] = []
    if not str(merged.get("name") or "").strip():
        missing.append("name")
    if not str(merged.get("resource_type") or "").strip():
        missing.append("resource_type")
    scope_level = merged.get("scope_level")
    if not scope_level:
        missing.append("scope_level")
    elif scope_level != "global" and not str(merged.get("scope_code") or "").strip():
        missing.append("scope_code")
    if not help_types:
        missing.append("help_types")
    if not _has_contact_method(merged.get("contact")):
        missing.append("contact")
    return missing


def compute_resource_status(merged: dict, help_types: list[str], archived: bool) -> str:
    """Auto-compute lifecycle status. 'archived' is explicit and wins; otherwise a
    resource is 'ready' iff all required fields are present, else 'pending'."""
    if archived:
        return "archived"
    return "ready" if not resource_missing_fields(merged, help_types) else "pending"


def _recompute_resource_status(cursor: sqlite3.Cursor, resource_id: str) -> None:
    cursor.execute("SELECT * FROM resources WHERE resource_id = ?", (resource_id,))
    row = cursor.fetchone()
    if not row:
        return
    contact = _json_loads_or({}, row["contact"])
    help_types = _get_resource_help_types(cursor, resource_id)
    status = compute_resource_status(
        {
            "name": row["name"],
            "resource_type": row["resource_type"],
            "scope_level": row["scope_level"],
            "scope_code": row["scope_code"],
            "contact": contact if isinstance(contact, dict) else {},
        },
        help_types,
        archived=row["status"] == "archived",
    )
    cursor.execute(
        "UPDATE resources SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE resource_id = ?",
        (status, resource_id),
    )


def _resource_row_to_dict(row: sqlite3.Row, help_types: list[str]) -> dict:
    import region_data
    contact = _json_loads_or({}, row["contact"])
    languages = _json_loads_or([], row["languages"])
    return {
        "resource_id": row["resource_id"],
        "name": row["name"],
        "resource_type": row["resource_type"],
        "description": row["description"],
        "contact": contact if isinstance(contact, dict) else {},
        "languages": languages if isinstance(languages, list) else [],
        "scope_level": row["scope_level"],
        "scope_code": row["scope_code"],
        "coverage": region_data.describe_scope(row["scope_level"], row["scope_code"]),
        "help_types": help_types,
        "status": row["status"],
        "missing_fields": resource_missing_fields(
            {
                "name": row["name"],
                "resource_type": row["resource_type"],
                "scope_level": row["scope_level"],
                "scope_code": row["scope_code"],
                "contact": contact if isinstance(contact, dict) else {},
            },
            help_types,
        ),
        "verified_at": row["verified_at"],
        "vetted_by": row["vetted_by"],
        "source_note": row["source_note"],
        "display_order": row["display_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_resource_help_types(cursor: sqlite3.Cursor, resource_id: str) -> list[str]:
    cursor.execute(
        "SELECT help_type FROM resource_help_types WHERE resource_id = ? ORDER BY help_type",
        (resource_id,),
    )
    return [r["help_type"] for r in cursor.fetchall()]


def get_resource(resource_id: str) -> dict | None:
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM resources WHERE resource_id = ?", (resource_id,))
        row = cursor.fetchone()
        if not row:
            return None
        help_types = _get_resource_help_types(cursor, resource_id)
        return _resource_row_to_dict(row, help_types)


def list_resources(status: str | None = None) -> list[dict]:
    with get_cursor() as cursor:
        if status:
            cursor.execute(
                "SELECT * FROM resources WHERE status = ? ORDER BY display_order, name",
                (status,),
            )
        else:
            cursor.execute("SELECT * FROM resources ORDER BY display_order, name")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            help_types = _get_resource_help_types(cursor, row["resource_id"])
            result.append(_resource_row_to_dict(row, help_types))
        return result


def create_resource(
    *,
    resource_id: str,
    name: str | None = None,
    resource_type: str | None = None,
    description: str | None = None,
    contact: dict | None = None,
    languages: list[str] | None = None,
    scope_level: str | None = None,
    scope_code: str | None = None,
    help_types: list[str] | None = None,
    verified_at: str | None = None,
    vetted_by: str | None = None,
    source_note: str | None = None,
    display_order: int = 0,
    archived: bool = False,
) -> dict:
    """Create a resource. Status is auto-computed from required-field completeness."""
    help_types = sorted(set(help_types or []))
    _validate_resource_scope(scope_level, scope_code)
    merged = {
        "name": name,
        "resource_type": resource_type,
        "scope_level": scope_level,
        "scope_code": scope_code,
        "contact": contact or {},
    }
    status = compute_resource_status(merged, help_types, archived)
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO resources (
                resource_id, name, resource_type, description, contact, languages,
                scope_level, scope_code, status, verified_at, vetted_by, source_note,
                display_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                resource_id,
                name,
                resource_type,
                description,
                json.dumps(contact or {}),
                json.dumps(languages or []),
                scope_level,
                scope_code,
                status,
                verified_at,
                vetted_by,
                source_note,
                display_order,
            ),
        )
        for ht in help_types:
            cursor.execute(
                "INSERT OR IGNORE INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
                (resource_id, ht),
            )
    return get_resource(resource_id)


_UNSET = object()


def _validate_resource_scope(scope_level: str | None, scope_code: str | None) -> None:
    if scope_code and not is_valid_scope(scope_level, scope_code):
        raise ValueError(f"invalid resource scope: {scope_level}/{scope_code}")


def update_resource(
    resource_id: str,
    *,
    name=_UNSET,
    resource_type=_UNSET,
    description=_UNSET,
    contact=_UNSET,
    languages=_UNSET,
    scope_level=_UNSET,
    scope_code=_UNSET,
    help_types=_UNSET,
    verified_at=_UNSET,
    vetted_by=_UNSET,
    source_note=_UNSET,
    display_order=_UNSET,
    archived=_UNSET,
) -> dict | None:
    """Partial update. Only provided fields change. Status is recomputed from the merged
    state unless an explicit archive flag is set. Returns the updated resource or None."""
    existing = get_resource(resource_id)
    if not existing:
        return None

    def pick(value, current):
        return current if value is _UNSET else value

    final_name = pick(name, existing["name"])
    final_type = pick(resource_type, existing["resource_type"])
    final_desc = pick(description, existing["description"])
    final_contact = pick(contact, existing["contact"])
    final_languages = pick(languages, existing["languages"])
    final_scope_level = pick(scope_level, existing["scope_level"])
    final_scope_code = pick(scope_code, existing["scope_code"])
    final_help_types = sorted(set(pick(help_types, existing["help_types"]) or []))
    final_verified_at = pick(verified_at, existing["verified_at"])
    final_vetted_by = pick(vetted_by, existing["vetted_by"])
    final_source_note = pick(source_note, existing["source_note"])
    final_display_order = pick(display_order, existing["display_order"])
    _validate_resource_scope(final_scope_level, final_scope_code)

    # Determine archive intent: explicit archived flag, or already-archived and not cleared.
    if archived is _UNSET:
        is_archived = existing["status"] == "archived"
    else:
        is_archived = bool(archived)

    merged = {
        "name": final_name,
        "resource_type": final_type,
        "scope_level": final_scope_level,
        "scope_code": final_scope_code,
        "contact": final_contact or {},
    }
    final_status = compute_resource_status(merged, final_help_types, is_archived)

    with get_cursor() as cursor:
        cursor.execute(
            """
            UPDATE resources SET
                name = ?, resource_type = ?, description = ?, contact = ?, languages = ?,
                scope_level = ?, scope_code = ?, status = ?, verified_at = ?, vetted_by = ?,
                source_note = ?, display_order = ?, updated_at = CURRENT_TIMESTAMP
            WHERE resource_id = ?
            """,
            (
                final_name,
                final_type,
                final_desc,
                json.dumps(final_contact or {}),
                json.dumps(final_languages or []),
                final_scope_level,
                final_scope_code,
                final_status,
                final_verified_at,
                final_vetted_by,
                final_source_note,
                final_display_order,
                resource_id,
            ),
        )
        if help_types is not _UNSET:
            cursor.execute("DELETE FROM resource_help_types WHERE resource_id = ?", (resource_id,))
            for ht in final_help_types:
                cursor.execute(
                    "INSERT OR IGNORE INTO resource_help_types (resource_id, help_type) VALUES (?, ?)",
                    (resource_id, ht),
                )
    return get_resource(resource_id)


def delete_resource(resource_id: str) -> bool:
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM resources WHERE resource_id = ?", (resource_id,))
        return cursor.rowcount > 0


def normalize_jurisdiction(value: str | None) -> str | None:
    """Resolve a free-text jurisdiction (country name/alias/ISO code) to an ISO code."""
    import region_data
    return region_data.resolve_country_code(value)


def search_resources(
    jurisdiction: str | None,
    help_type: str,
    language: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Faceted lookup: ready resources whose coverage scope contains the user's country
    and that provide the requested help type. Ranked by scope specificity, then verified,
    then (optionally) language match, then display order."""
    import region_data

    sql_limit = max(0, int(limit))
    fetch_limit = min(max(sql_limit * 4, sql_limit), 100) if language and sql_limit else sql_limit
    country_code = region_data.resolve_country_code(jurisdiction)
    ancestors = region_data.region_ancestors(country_code)

    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT r.* FROM resources r
            JOIN resource_help_types h ON h.resource_id = r.resource_id
            WHERE r.status = 'ready' AND h.help_type = ?
              AND (
                   (r.scope_level = 'country'   AND r.scope_code = ?)
                OR (r.scope_level = 'subregion' AND r.scope_code = ?)
                OR (r.scope_level = 'region'    AND r.scope_code = ?)
                OR (r.scope_level = 'global')
              )
            ORDER BY
              CASE r.scope_level
                WHEN 'country' THEN 0 WHEN 'subregion' THEN 1 WHEN 'region' THEN 2 ELSE 3 END,
              CASE WHEN r.verified_at IS NOT NULL THEN 0 ELSE 1 END,
              r.display_order
            LIMIT ?
            """,
            (
                help_type,
                ancestors["country_code"],
                ancestors["subregion_code"],
                ancestors["region_code"],
                fetch_limit,
            ),
        )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            help_types = _get_resource_help_types(cursor, row["resource_id"])
            results.append(_resource_row_to_dict(row, help_types))

    # Optional language preference should not outrank local coverage or verified status.
    if language:
        scope_rank = {"country": 0, "subregion": 1, "region": 2, "global": 3}
        results.sort(
            key=lambda r: (
                scope_rank.get(r.get("scope_level"), 3),
                0 if r.get("verified_at") else 1,
                0 if language in (r.get("languages") or []) else 1,
                r.get("display_order") or 0,
            )
        )

    return results[:sql_limit]


# --- Help-type vocabulary (operator-extensible) ---

def list_help_types(include_inactive: bool = True) -> list[dict]:
    with get_cursor() as cursor:
        if include_inactive:
            cursor.execute("SELECT * FROM help_types ORDER BY display_order, key")
        else:
            cursor.execute("SELECT * FROM help_types WHERE is_active = 1 ORDER BY display_order, key")
        return [
            {
                "key": r["key"],
                "label": r["label"],
                "description": r["description"],
                "display_order": r["display_order"],
                "is_active": bool(r["is_active"]),
            }
            for r in cursor.fetchall()
        ]


def get_help_type(key: str) -> dict | None:
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM help_types WHERE key = ?", (key,))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "key": r["key"],
            "label": r["label"],
            "description": r["description"],
            "display_order": r["display_order"],
            "is_active": bool(r["is_active"]),
        }


def upsert_help_type(
    key: str,
    label: str,
    description: str | None = None,
    display_order: int = 0,
    is_active: bool = True,
) -> dict:
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO help_types (key, label, description, display_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                label = excluded.label,
                description = excluded.description,
                display_order = excluded.display_order,
                is_active = excluded.is_active,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, label, description, display_order, 1 if is_active else 0),
        )
    return get_help_type(key)


def delete_help_type(key: str) -> bool:
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT resource_id FROM resource_help_types WHERE help_type = ?",
            (key,),
        )
        affected_resource_ids = [row["resource_id"] for row in cursor.fetchall()]
        cursor.execute("DELETE FROM help_types WHERE key = ?", (key,))
        deleted = cursor.rowcount > 0
        if deleted:
            for resource_id in affected_resource_ids:
                _recompute_resource_status(cursor, resource_id)
        return deleted


CORE_HELP_TYPES = [
    {"key": "legal", "label": "Legal", "description": "Lawyers, legal aid, representation, habeas filings."},
    {"key": "humanitarian", "label": "Humanitarian", "description": "Human-rights orgs, UN bodies, advocacy and protection."},
    {"key": "medical", "label": "Medical", "description": "Clinics, doctors, trauma and emergency care."},
    {"key": "food", "label": "Food", "description": "Food assistance and nutrition support."},
    {"key": "shelter", "label": "Shelter", "description": "Safe housing, refuge, relocation support."},
    {"key": "financial", "label": "Financial", "description": "Financial aid, support for the debanked, emergency funds."},
    {"key": "psychosocial", "label": "Psychosocial", "description": "Mental health, counseling, trauma support."},
    {"key": "other", "label": "Other", "description": "Resources that do not fit the categories above."},
]


def seed_help_types(defaults: list[dict] | None = None) -> None:
    """Idempotently seed the core help-type vocabulary (operators can extend/edit later)."""
    defaults = defaults if defaults is not None else CORE_HELP_TYPES
    with get_cursor() as cursor:
        for i, ht in enumerate(defaults):
            cursor.execute(
                """
                INSERT OR IGNORE INTO help_types (key, label, description, display_order, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (ht["key"], ht["label"], ht.get("description"), ht.get("display_order", i)),
            )
    logger.info("Default help types seeded")


def seed_country_regions() -> None:
    """Idempotently seed the ISO 3166 / UN M49 region map from region_data.py."""
    import region_data
    with get_cursor() as cursor:
        for row in region_data.iter_country_region_rows():
            cursor.execute(
                """
                INSERT OR IGNORE INTO country_regions
                    (country_code, country_name, subregion_code, subregion_name, region_code, region_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )
    logger.info("Country/region map seeded")
