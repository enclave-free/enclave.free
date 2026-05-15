"""Backend-readable content artifact encryption for active storage."""

import base64
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
from typing import Iterator

from Crypto.Cipher import AES

import database


ARTIFACT_PREFIX = b"sanctum-artifact::v1::"
ARTIFACT_ENCRYPTION_KEY = "DOCUMENT_ARTIFACT_ENCRYPTION"
CONTENT_ENCRYPTION_KEY = "CONTENT_ENCRYPTION_KEY"


def artifact_encryption_posture() -> str:
    value = str(
        database.get_deployment_config_value(ARTIFACT_ENCRYPTION_KEY)
        or database.get_setting(ARTIFACT_ENCRYPTION_KEY)
        or os.getenv(ARTIFACT_ENCRYPTION_KEY, "required")
    ).strip().lower()
    if value == "disabled":
        return "disabled"
    return "required"


def _content_encryption_key_value() -> str:
    return (
        database.get_deployment_config_value(CONTENT_ENCRYPTION_KEY)
        or os.getenv(CONTENT_ENCRYPTION_KEY, "")
    ).strip()


def content_encryption_key_configured() -> bool:
    return bool(_content_encryption_key_value())


def content_encryption_status() -> dict:
    if content_encryption_key_configured():
        return {
            "status": "configured",
            "summary": "Content Encryption Key is configured for backend-readable active content storage.",
        }
    return {
        "status": "not_configured",
        "summary": "Content Encryption Key is not configured; encrypted active content writes cannot proceed.",
    }


def artifact_encryption_status() -> dict:
    posture = artifact_encryption_posture()
    if posture == "disabled":
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
    key = _content_encryption_key_value()
    if not key:
        raise RuntimeError("Content Encryption Key is required for encrypted artifact storage.")
    return _derive_artifact_key(key)


def _derive_artifact_key(key: str) -> bytes:
    pseudo_random_key = hmac.new(
        b"sanctum/artifact/v1",
        key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        pseudo_random_key,
        b"sanctum/artifact/v1" + b"\x01",
        hashlib.sha256,
    ).digest()


def _legacy_key_bytes() -> bytes:
    key = _content_encryption_key_value()
    if not key:
        raise RuntimeError("Content Encryption Key is required for encrypted artifact storage.")
    return hashlib.sha256(key.encode("utf-8")).digest()


def encrypt_bytes(plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    cipher = AES.new(_key_bytes(), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    payload = base64.b64encode(nonce + tag + ciphertext)
    return ARTIFACT_PREFIX + payload


def is_encrypted_artifact(content: bytes) -> bool:
    return content.startswith(ARTIFACT_PREFIX)


def decrypt_bytes(content: bytes) -> bytes:
    """Decrypt ARTIFACT_PREFIX-prefixed content, returning unprefixed input unchanged.

    decrypt_bytes only verifies AES-GCM integrity when ARTIFACT_PREFIX is present.
    Callers that need to know whether plaintext was verified should check
    is_encrypted_artifact before treating the output as authenticated plaintext.
    """
    if not is_encrypted_artifact(content):
        return content
    raw = base64.b64decode(content[len(ARTIFACT_PREFIX):])
    nonce = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    try:
        cipher = AES.new(_key_bytes(), AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError:
        cipher = AES.new(_legacy_key_bytes(), AES.MODE_GCM, nonce=nonce)
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
