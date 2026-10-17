"""Per-principal API keys (ADR-0004 permission tiers). Only a SHA-256 hash is stored; raw keys are
returned once at creation and never logged."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request


@dataclass(frozen=True)
class Principal:
    id: uuid.UUID
    name: str
    kind: str


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_key() -> str:
    return "bk_" + secrets.token_urlsafe(32)


def current_principal(request: Request, authorization: str = Header(default="")) -> Principal:
    scheme, _, raw = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw:
        raise HTTPException(401, {"code": "UNAUTHENTICATED", "message": "missing bearer API key"})
    with request.app.state.pool.connection() as c:
        row = c.execute("SELECT id, name, kind, disabled_at, (key_expires_at <= clock_timestamp()) AS expired"
                        " FROM principals WHERE api_key_hash = %s", (hash_key(raw),)).fetchone()
    if row is None:
        raise HTTPException(401, {"code": "UNAUTHENTICATED", "message": "unknown API key"})
    if row["expired"]:        # ADR-0009 C2: a distinct code lets a client send the user to rotate/re-issue
        raise HTTPException(401, {"code": "KEY_EXPIRED", "message": "API key has expired"})
    if row["disabled_at"] is not None:
        raise HTTPException(401, {"code": "PRINCIPAL_DISABLED", "message": "this principal has been disabled"})
    return Principal(row["id"], row["name"], row["kind"])


def require_admin(x_admin_token: str = Header(default="")) -> None:
    """Bootstrap/demo-only endpoints (creating principals, resetting fixtures)."""
    expected = os.environ.get("BK_ADMIN_TOKEN", "")
    if not expected or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(403, {"code": "ADMIN_ONLY", "message": "admin token required"})


Caller = Depends(current_principal)
