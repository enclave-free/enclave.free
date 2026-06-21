"""
Impersonation — admin "act as a test user".

The Test & Feedback module lets an admin switch into a non-admin persona and chat
as that user against Sage. We make the test user a *real, instance-owned* identity:

- Its Nostr keypair is DERIVED deterministically from the server secret and the
  admin's pubkey (a per-persona subkey), so the test user transparently belongs to
  this admin/instance and can be re-derived, never guessed.
- Chatting as them uses a real, signed user session token (the same itsdangerous
  contract Sage verifies), sent as `Authorization: Bearer`. Sage prefers the bearer
  over the cookie, so only the chat requests are scoped to the test user — the
  admin's own cookie session is untouched.

Safety: issue_session_token refuses to mint a session for any user whose pubkey is
not the instance-derived subkey, so this can never be used to impersonate a real user.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple


class ImpersonationUnavailable(RuntimeError):
    """Raised when impersonation is requested but cannot be satisfied."""


def _derive_seed(admin_pubkey: str, user_type_id: Optional[int]) -> bytes:
    from auth import SECRET_KEY

    label = (
        "enclave-test-user-subkey:v1:"
        f"{admin_pubkey}:{user_type_id if user_type_id is not None else 'none'}"
    )
    return hmac.new(SECRET_KEY.encode(), label.encode(), hashlib.sha256).digest()


def derive_test_user_keypair(
    admin_pubkey: str, user_type_id: Optional[int]
) -> Tuple[bytes, str]:
    """Deterministically derive a secp256k1 subkey for a test persona.

    Returns (private_key_bytes, x_only_pubkey_hex). HMAC output is a valid scalar
    with overwhelming probability; the loop only guards the astronomically unlikely
    invalid case, and does so deterministically so the key stays reproducible.
    """
    from coincurve import PrivateKey

    seed = _derive_seed(admin_pubkey, user_type_id)
    for counter in range(256):
        candidate = (
            seed if counter == 0 else hashlib.sha256(seed + bytes([counter])).digest()
        )
        try:
            priv = PrivateKey(candidate)
        except ValueError:
            continue
        pub_x_only = priv.public_key.format(compressed=True)[1:].hex()
        return priv.secret, pub_x_only
    raise ImpersonationUnavailable("Could not derive a valid test-user subkey")


def derive_test_user_pubkey(admin_pubkey: str, user_type_id: Optional[int]) -> str:
    return derive_test_user_keypair(admin_pubkey, user_type_id)[1]


def is_available() -> bool:
    return True


def _test_user_email(user_type_id: Optional[int]) -> str:
    return (
        f"test-user+type{user_type_id}@enclave.test"
        if user_type_id is not None
        else "test-user@enclave.test"
    )


def issue_session_token(*, user_id: int, issued_by_pubkey: str) -> dict[str, Any]:
    """Mint a real, signed user session token scoped to the test user.

    Refuses unless the user's pubkey is exactly the subkey this instance derives
    for the admin + persona — so it can never impersonate a real (non-test) user.
    """
    import auth
    import database
    from nostr_keys import normalize_pubkey

    user = database.get_user(user_id)
    if not user:
        raise ImpersonationUnavailable("Test user not found")

    expected_pubkey = derive_test_user_pubkey(issued_by_pubkey, user.get("user_type_id"))
    actual_pubkey = user.get("pubkey")
    if not actual_pubkey or normalize_pubkey(actual_pubkey) != expected_pubkey:
        raise ImpersonationUnavailable(
            "Refusing to impersonate a user that is not an instance-derived test user"
        )

    email = user.get("email") or _test_user_email(user.get("user_type_id"))
    token = auth.create_session_token(user_id, email)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=auth.SESSION_MAX_AGE)
    ).isoformat()
    return {"token": token, "expires_at": expires_at}
