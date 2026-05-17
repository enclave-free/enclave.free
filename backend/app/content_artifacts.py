from __future__ import annotations

"""Backend-readable content artifact encryption for active storage."""

import base64
import binascii
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
from typing import Iterator

from Crypto.Cipher import AES

import database


ARTIFACT_PREFIX = b"enclave-artifact::v1::"
OLD_ARTIFACT_PREFIX = b"sanctum-artifact::v1::"
ARTIFACT_ENCRYPTION_KEY = "DOCUMENT_ARTIFACT_ENCRYPTION"
CONTENT_ENCRYPTION_KEY = "CONTENT_ENCRYPTION_KEY"
ARTIFACT_KEY_INFO = b"enclave/artifact/v1"


def _artifact_encryption_setting_value() -> str | None:
    value = (
        database.get_deployment_config_value(ARTIFACT_ENCRYPTION_KEY)
        or database.get_setting(ARTIFACT_ENCRYPTION_KEY)
        or os.getenv(ARTIFACT_ENCRYPTION_KEY)
    )
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _artifact_encryption_is_implicit_auto() -> bool:
    return _artifact_encryption_setting_value() in {None, "opportunistic", "auto", "enabled_if_configured"}


def artifact_encryption_posture() -> str:
    value = _artifact_encryption_setting_value() or "auto"
    if value in {"disabled", "required"}:
        return value
    if value in {"opportunistic", "auto", "enabled_if_configured"}:
        return "disabled" if not content_encryption_key_configured() else "required"
    if not content_encryption_key_configured():
        return "disabled"
    return "required"


def _content_encryption_key_value() -> str:
    return (
        database.get_deployment_config_value(CONTENT_ENCRYPTION_KEY)
        or os.getenv(CONTENT_ENCRYPTION_KEY, "")
    ).strip()


def content_encryption_key_configured() -> bool:
    return bool(_content_encryption_key_value())


def require_content_encryption_key() -> None:
    """Raise if backend-readable active content encryption is not configured."""
    if not content_encryption_key_configured():
        raise RuntimeError("Content Encryption Key is required for encrypted active content storage.")


def content_encryption_status() -> dict:
    if content_encryption_key_configured():
        return {
            "status": "configured",
            "summary": "Content Encryption Key is configured for backend-readable active content storage.",
        }
    return {
        "status": "not_configured",
        "summary": "Content Encryption Key is not configured; active content is stored as plaintext by default.",
    }


def artifact_encryption_status() -> dict:
    posture = artifact_encryption_posture()
    if posture == "disabled":
        if _artifact_encryption_is_implicit_auto() and not content_encryption_key_configured():
            return {
                "posture": "disabled",
                "status": "not_configured",
                "summary": "Artifact encryption is not configured because no Content Encryption Key is configured.",
            }
        return {
            "posture": "disabled",
            "status": "plaintext_by_operator_choice",
            "summary": "Uploaded Document artifacts are stored as plaintext by explicit Operator choice.",
        }
    if content_encryption_key_configured():
        return {
            "posture": "required",
            "status": "encrypted",
            "summary": "Uploaded Document artifacts are encrypted in active storage for new writes.",
        }
    return {
        "posture": "required",
        "status": "not_configured",
        "summary": "Artifact encryption is required, but no Content Encryption Key is configured.",
    }


def _key_bytes() -> bytes:
    require_content_encryption_key()
    key = _content_encryption_key_value()
    return _derive_artifact_key(key, ARTIFACT_KEY_INFO)


def _derive_artifact_key(key: str, info: bytes) -> bytes:
    pseudo_random_key = hmac.new(
        info,
        key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        pseudo_random_key,
        info + b"\x01",
        hashlib.sha256,
    ).digest()


def encrypt_bytes(plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    cipher = AES.new(_key_bytes(), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    payload = base64.b64encode(nonce + tag + ciphertext)
    return ARTIFACT_PREFIX + payload


def is_encrypted_artifact(content: bytes) -> bool:
    return content.startswith((ARTIFACT_PREFIX, OLD_ARTIFACT_PREFIX))


def _is_legacy_encrypted_artifact(content: bytes) -> bool:
    if not content.startswith(OLD_ARTIFACT_PREFIX):
        return False
    try:
        raw = base64.b64decode(content[len(OLD_ARTIFACT_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(raw) > 28


def decrypt_bytes(content: bytes) -> bytes:
    """Decrypt ARTIFACT_PREFIX-prefixed content, returning unprefixed input unchanged.

    decrypt_bytes only verifies AES-GCM integrity when ARTIFACT_PREFIX is present.
    Callers that need to know whether plaintext was verified should check
    is_encrypted_artifact before treating the output as authenticated plaintext.
    """
    if content.startswith(OLD_ARTIFACT_PREFIX):
        detail = (
            "valid legacy nonce/tag/ciphertext envelope"
            if _is_legacy_encrypted_artifact(content)
            else "malformed legacy envelope"
        )
        raise ValueError(
            "Legacy encrypted document artifact format sanctum-artifact::v1 is not supported by "
            f"the active reader ({detail}). Run the confidentiality migration to rewrite this artifact."
        )
    if not is_encrypted_artifact(content):
        return content
    raw = base64.b64decode(content[len(ARTIFACT_PREFIX):])
    nonce = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    cipher = AES.new(_key_bytes(), AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def encode_for_storage(content: bytes) -> bytes:
    if artifact_encryption_posture() == "disabled":
        return content
    return encrypt_bytes(content)


def read_artifact_bytes(path: Path) -> bytes:
    return decrypt_bytes(path.read_bytes())


@contextmanager
def processing_path(path: Path, temp_dir: Path | str | None = None) -> Iterator[Path]:
    content = path.read_bytes()
    if not is_encrypted_artifact(content):
        yield path
        return

    suffix = path.suffix
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as temp:
            temp.write(decrypt_bytes(content))
            temp_path = Path(temp.name)
        yield temp_path
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
