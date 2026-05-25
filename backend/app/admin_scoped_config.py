"""
Admin-facing Scoped Config Context API for the Configuration Assistant.

Browsers call this route instead of assembling scoped admin configuration
context locally. The Enclave Control Plane remains the semantic authority.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth
import database
from scoped_config_context import (
    ScopedConfigAuthorizationError,
    ScopedConfigMode,
    ScopedConfigScope,
    build_scoped_config_context,
)

router = APIRouter(prefix="/admin", tags=["admin-scoped-config"])


class AdminScopedConfigContextRequest(BaseModel):
    query: str
    mode: ScopedConfigMode = "auto"
    requested_scopes: list[ScopedConfigScope] | None = None


class AdminScopedConfigSecretPolicy(BaseModel):
    mode: str = "masked"


class AdminScopedConfigContextResponse(BaseModel):
    version: int
    primary_scope: ScopedConfigScope
    included_scopes: list[ScopedConfigScope]
    context_text: str
    warnings: list[str]
    generated_at: str
    secret_policy: AdminScopedConfigSecretPolicy
    deployment_secret_keys: list[str]


def _admin_actor(admin: dict) -> dict:
    """Map an authenticated admin session to internal scoped-config actor context."""
    return {
        "id": admin["id"],
        "type": "admin",
        "approved": True,
        "pubkey": admin.get("pubkey"),
    }


def _deployment_secret_keys() -> list[str]:
    """Return deployment secret keys for client-side redaction metadata only."""
    return sorted(
        item["key"]
        for item in database.get_all_deployment_config()
        if item.get("is_secret")
    )


@router.post("/scoped-config-context", response_model=AdminScopedConfigContextResponse)
async def admin_scoped_config_context(
    payload: AdminScopedConfigContextRequest,
    admin: dict = Depends(auth.require_admin),
) -> AdminScopedConfigContextResponse:
    """
    Build server-owned Scoped Config Context for admin UI surfaces.

    Parameters:
        payload: Admin query, optional mode, and optional explicit scope hints.
        admin: Authenticated admin session from require_admin.
    """
    try:
        result = build_scoped_config_context(
            query=payload.query,
            actor=_admin_actor(admin),
            mode=payload.mode,
            requested_scopes=payload.requested_scopes,
        )
    except ScopedConfigAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    secret_policy = result.get("secret_policy") or {"mode": "masked"}
    return AdminScopedConfigContextResponse(
        version=result["version"],
        primary_scope=result["primary_scope"],
        included_scopes=result["included_scopes"],
        context_text=result["context_text"],
        warnings=result["warnings"],
        generated_at=result["generated_at"],
        secret_policy=AdminScopedConfigSecretPolicy(mode=secret_policy.get("mode", "masked")),
        deployment_secret_keys=_deployment_secret_keys(),
    )
