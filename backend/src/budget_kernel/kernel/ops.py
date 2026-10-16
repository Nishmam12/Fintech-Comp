"""Kernel operations. The only code that mutates grants / transactions / ledger (ADR-0001, ADR-0005).

Everything here is deterministic and trusts nothing a model produced: callers pass already
validated primitives, and every decision is recomputed from authoritative database state.
All time comparisons use ctx.now (read after the mandate lock), never SQL now().
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from psycopg.types.json import Jsonb

from .errors import (Conflict, DelegationRejected, Forbidden, IdempotencyConflict, NotFound,
                     ValidationFailed, ensure)
from .funds import reclaim_subtree, release_tx
from .scope import MAX_BIGINT, is_subset, validate_scope
from .tx import RESERVE_TTL_SECONDS, Ctx, audit, kernel_tx, mandate_of_grant, mandate_of_tx, movement

MAX_DEPTH = 4
MAX_PENDING_REVIEWS = 20  # per grant; proposals awaiting the owner (ADR-0008 review: inbox-flooding guard)


def _amount(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not 0 < v <= MAX_BIGINT:
        raise ValidationFailed("amount must be a positive integer in minor units", code="BAD_AMOUNT")
    return v


def _text(v: Any, name: str) -> str:
    """Case-insensitive business identifiers (recipient, category, currency)."""
    if not isinstance(v, str) or not v.strip() or len(v) > 200:
        raise ValidationFailed(f"{name} must be a non-empty string", code=f"BAD_{name.upper()}")
    return v.strip().lower()


def _key(v: Any) -> str:
    """Idempotency keys are opaque and case-sensitive: never lowercase them."""
    if not isinstance(v, str) or not v.strip() or len(v) > 200:
        raise ValidationFailed("idempotency_key must be a non-empty string", code="BAD_IDEMPOTENCY_KEY")
    return v.strip()


def _utc(dt: datetime) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise ValidationFailed("datetime must be timezone-aware", code="BAD_DATETIME")
    return dt.astimezone(timezone.utc)


def _hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _audit_outside(pool, mandate_id, kind, actor, subject, **detail) -> None:
    """Audit a refused request in its own short transaction (the main one rolled back)."""
    with pool.connection() as conn:
        with conn.transaction():
            audit(conn, mandate_id, kind, actor, subject, **detail)


# --------------------------------------------------------------------------- mandate

def create_mandate(pool, *, owner_principal_id, currency: str, total: int, protected_reserve: int,
                   expires_at: datetime, scope: dict) -> dict:
    total = _amount(total)
    if (isinstance(protected_reserve, bool) or not isinstance(protected_reserve, int)
            or not 0 <= protected_reserve < total):
        raise ValidationFailed("protected_reserve must be >= 0 and < total", code="BAD_RESERVE")
    currency = _text(currency, "currency").upper()
    if len(currency) != 3:
        raise ValidationFailed("currency must be 3 letters", code="BAD_CURRENCY")
    scope, expires_at = validate_scope(scope), _utc(expires_at)
    mid, gid = uuid.uuid4(), uuid.uuid4()
    with pool.connection() as conn:
        with conn.transaction():
            if not conn.execute("SELECT %s > clock_timestamp() AS ok", (expires_at,)).fetchone()["ok"]:
                raise ValidationFailed("expires_at must be in the future", code="BAD_EXPIRY")
            owner = conn.execute("SELECT kind FROM principals WHERE id = %s", (owner_principal_id,)).fetchone()
            if owner is None:
                raise NotFound("owner principal not found", code="PRINCIPAL_NOT_FOUND")
            if owner["kind"] != "human":
                # Tier T0 (ADR-0004): only a human may create authority. An agent or service minting
                # its own mandate would bypass every delegation limit.
                raise Forbidden("only human principals may create mandates", code="OWNER_MUST_BE_HUMAN")
            conn.execute(
                "INSERT INTO mandates(id, owner_principal_id, currency, total, protected_reserve, expires_at)"
                " VALUES (%s,%s,%s,%s,%s,%s)",
                (mid, owner_principal_id, currency, total, protected_reserve, expires_at))
            avail = total - protected_reserve
            conn.execute(
                "INSERT INTO grants(id, mandate_id, parent_id, path, depth, holder_principal_id, available,"
                " expires_at, scope) VALUES (%s,%s,NULL,%s,0,%s,%s,%s,%s)",
                (gid, mid, [gid], owner_principal_id, avail, expires_at, Jsonb(scope)))
            movement(conn, mid, "mint", avail, to_grant=gid, to_bucket="available", from_bucket="mandate",
                     actor=owner_principal_id)
            movement(conn, mid, "protect", protected_reserve, to_bucket="protected", from_bucket="mandate",
                     actor=owner_principal_id)
            audit(conn, mid, "MANDATE_CREATED", owner_principal_id, mid, total=total,
                  protected_reserve=protected_reserve, currency=currency)
    return {"mandate_id": mid, "root_grant_id": gid, "available": avail}


# --------------------------------------------------------------------------- delegation

def delegate(pool, *, parent_grant_id, actor, holder_principal_id, amount: int, expires_at: datetime,
             scope: dict, idempotency_key: str) -> dict:
    amount, scope, expires_at = _amount(amount), validate_scope(scope), _utc(expires_at)
    key = _key(idempotency_key)
    phash = _hash({"parent": str(parent_grant_id), "holder": str(holder_principal_id), "amount": amount,
                   "expires_at": expires_at.isoformat(), "scope": scope})
    mid = mandate_of_grant(pool, parent_grant_id)
    try:
        with kernel_tx(pool, mid) as ctx:
            c = ctx.conn
            parent = c.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (parent_grant_id,)).fetchone()
            if parent["holder_principal_id"] != actor:
                raise Forbidden("only the grant holder may delegate", code="NOT_GRANT_HOLDER")
            existing = c.execute("SELECT * FROM grants WHERE parent_id = %s AND idempotency_key = %s",
                                 (parent_grant_id, key)).fetchone()
            if existing:
                if existing["payload_hash"] != phash:
                    raise IdempotencyConflict("idempotency key reused with a different delegation")
                return {"grant_id": existing["id"], "replayed": True}
            problem = _delegation_problem(ctx, parent, amount, expires_at, scope, holder_principal_id)
            if problem:
                raise DelegationRejected(problem, code=problem)
            gid = uuid.uuid4()
            n = c.execute(
                "UPDATE grants SET available = available - %s WHERE id = %s AND status = 'active'"
                " AND available >= %s", (amount, parent_grant_id, amount)).rowcount
            ensure(n == 1, "delegate: conditional debit failed")
            c.execute(
                "INSERT INTO grants(id, mandate_id, parent_id, path, depth, holder_principal_id, available,"
                " expires_at, scope, idempotency_key, payload_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (gid, mid, parent_grant_id, parent["path"] + [gid], parent["depth"] + 1, holder_principal_id,
                 amount, expires_at, Jsonb(scope), key, phash))
            movement(c, mid, "delegate", amount, from_grant=parent_grant_id, from_bucket="available",
                     to_grant=gid, to_bucket="available", actor=actor)
            audit(c, mid, "GRANT_DELEGATED", actor, gid, parent=str(parent_grant_id), amount=amount)
            return {"grant_id": gid, "replayed": False}
    except (IdempotencyConflict, DelegationRejected, Forbidden) as exc:
        _audit_outside(pool, mid, getattr(exc, "code", "REFUSED"), actor, parent_grant_id, error=str(exc))
        raise


def _delegation_problem(ctx: Ctx, parent, amount, expires_at, scope, holder) -> str | None:
    problem = _path_problem(ctx, parent)
    if problem:
        return problem
    if not parent["scope"]["can_delegate"]:
        return "PARENT_CANNOT_DELEGATE"
    if parent["depth"] >= MAX_DEPTH:
        return "MAX_DEPTH_EXCEEDED"
    if amount > parent["available"]:
        return "INSUFFICIENT_FUNDS"
    if expires_at > parent["expires_at"]:
        return "EXPIRY_EXCEEDS_PARENT"
    if expires_at <= ctx.now:
        return "EXPIRY_IN_PAST"
    if not is_subset(scope, parent["scope"]):
        return "SCOPE_WIDER_THAN_PARENT"
    if ctx.conn.execute("SELECT 1 FROM principals WHERE id = %s", (holder,)).fetchone() is None:
        return "HOLDER_NOT_FOUND"
    return None


def _path_problem(ctx: Ctx, grant) -> str | None:
    """Every grant on the path (and the mandate) must be active and unexpired, read under the lock."""
    if ctx.mandate["status"] != "active":
        return "MANDATE_FROZEN"
    if ctx.mandate["expires_at"] <= ctx.now:
        return "MANDATE_EXPIRED"
    rows = ctx.conn.execute(
        "SELECT id, scope, status, (expires_at <= %s) AS expired FROM grants WHERE id = ANY(%s)",
        (ctx.now, grant["path"])).fetchall()
    if len(rows) != len(grant["path"]):
        return "PATH_BROKEN"
    ctx.scopes.update({r["id"]: r["scope"] for r in rows})   # reused by the ADR-0008 checks: no extra round trip
    for r in rows:
        if r["status"] == "revoked":
            return "GRANT_REVOKED"
        if r["status"] == "expired" or r["expired"]:
            return "GRANT_EXPIRED"
    return None


# --------------------------------------------------------------------------- authorize

def authorize(pool, *, grant_id, actor, amount: int, currency: str, recipient: str, category: str,
              idempotency_key: str, needs_review: bool = False, proposal: dict | None = None) -> dict:
    """Decide a spend request from authoritative state. A model proposal never reaches this far
    with trusted fields: the caller passes plain values and `proposal` is stored for display only.

    `needs_review` is caller policy (e.g. the router flagged ambiguity): it can only make the
    outcome stricter (no funds held until an owner approves), never looser."""
    amount = _amount(amount)
    currency = _text(currency, "currency").upper()
    recipient, category = _text(recipient, "recipient"), _text(category, "category")
    key = _key(idempotency_key)
    phash = _hash({"grant": str(grant_id), "amount": amount, "currency": currency, "recipient": recipient,
                   "category": category, "needs_review": bool(needs_review)})
    mid = mandate_of_grant(pool, grant_id)
    try:
        with kernel_tx(pool, mid) as ctx:
            c = ctx.conn
            g = c.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (grant_id,)).fetchone()
            if g["holder_principal_id"] != actor:
                raise Forbidden("only the grant holder may authorize spends", code="NOT_GRANT_HOLDER")
            prior = c.execute("SELECT * FROM transactions WHERE grant_id = %s AND idempotency_key = %s",
                              (grant_id, key)).fetchone()
            if prior:
                if prior["payload_hash"] != phash:
                    raise IdempotencyConflict("idempotency key reused with a different request")
                return _decision(prior, replayed=True)  # stored decision replayed, never re-evaluated
            reason = _authorize_problem(ctx, g, amount, currency, recipient, category)
            if reason:
                tx = _insert_tx(ctx, g, amount, currency, recipient, category, "rejected", key, phash,
                                reason=reason, proposal=proposal)
                audit(c, mid, "TX_REJECTED", actor, tx["id"], reason=reason, amount=amount)
                return _decision(tx)
            held = _hold_reason(ctx, g, actor, amount, needs_review)
            if held and c.execute("SELECT count(*) AS n FROM transactions WHERE grant_id = %s AND state = 'proposed'",
                                  (grant_id,)).fetchone()["n"] >= MAX_PENDING_REVIEWS:
                # Held requests cost the holder nothing; without a cap one agent could bury the owner's
                # approval inbox. Refusing is fail-closed: nothing is reserved either way.
                reason = "TOO_MANY_PENDING_REVIEWS"
                tx = _insert_tx(ctx, g, amount, currency, recipient, category, "rejected", key, phash,
                                reason=reason, proposal=proposal)
                audit(c, mid, "TX_REJECTED", actor, tx["id"], reason=reason, amount=amount)
                return _decision(tx)
            if held:
                tx = _insert_tx(ctx, g, amount, currency, recipient, category, "proposed", key, phash,
                                proposal=proposal, review_reason=held)
                audit(c, mid, "TX_PROPOSED", actor, tx["id"], amount=amount, review_reason=held)
                return _decision(tx)
            _reserve(ctx, g["id"], amount)
            tx = _insert_tx(ctx, g, amount, currency, recipient, category, "reserved", key, phash,
                            proposal=proposal, ttl=True)
            movement(c, mid, "reserve", amount, from_grant=grant_id, from_bucket="available", to_grant=grant_id,
                     to_bucket="reserved", transaction_id=tx["id"], actor=actor)
            audit(c, mid, "TX_RESERVED", actor, tx["id"], amount=amount, recipient=recipient, category=category)
            return _decision(tx)
    except (IdempotencyConflict, Forbidden) as exc:
        _audit_outside(pool, mid, getattr(exc, "code", "REFUSED"), actor, grant_id, error=str(exc))
        raise


def _reserve(ctx: Ctx, grant_id, amount: int) -> None:
    n = ctx.conn.execute(
        "UPDATE grants SET available = available - %s, reserved = reserved + %s"
        " WHERE id = %s AND status = 'active' AND available >= %s",
        (amount, amount, grant_id, amount)).rowcount
    ensure(n == 1, "conditional reserve failed")


def _authorize_problem(ctx: Ctx, g, amount, currency, recipient, category) -> str | None:
    problem = _path_problem(ctx, g)
    if problem:
        return problem
    if currency != ctx.mandate["currency"].strip().upper():
        return "CURRENCY_MISMATCH"
    sc = g["scope"]
    if category not in sc["categories"]:
        return "CATEGORY_NOT_ALLOWED"
    if recipient not in sc["recipients"]:
        return "RECIPIENT_NOT_ALLOWED"
    if amount > sc["per_tx_limit"]:
        return "PER_TX_LIMIT_EXCEEDED"
    if _velocity_exceeded(ctx, g, amount):
        return "VELOCITY_LIMIT_EXCEEDED"
    if amount > g["available"]:
        return "INSUFFICIENT_FUNDS"
    return None


def _path_scopes(ctx: Ctx, g) -> list[dict]:
    """(id, scope) of every grant on the request's path, self included. Normally served from the cache the
    path check filled under this same lock; queried only if a caller skipped the path check."""
    if not all(gid in ctx.scopes for gid in g["path"]):
        ctx.scopes.update({r["id"]: r["scope"] for r in ctx.conn.execute(
            "SELECT id, scope FROM grants WHERE id = ANY(%s)", (g["path"],))})
    return [{"id": gid, "scope": ctx.scopes[gid]} for gid in g["path"]]


def _velocity_exceeded(ctx: Ctx, g, amount: int) -> bool:
    """ADR-0008: for every grant on the path that sets a window, committed spend across ITS WHOLE SUBTREE
    in the rolling window, plus this request, must stay within window_limit. Committed = reserved, submitted
    or settled, dated by reserved_at. Read under the mandate lock, so concurrent requests cannot both pass."""
    for row in _path_scopes(ctx, g):
        sc = row["scope"]
        if "window_limit" not in sc:
            continue
        spent = ctx.conn.execute(
            "SELECT coalesce(sum(t.amount), 0)::bigint AS s FROM transactions t JOIN grants x ON x.id = t.grant_id"
            " WHERE t.mandate_id = %s AND x.path @> ARRAY[%s]::uuid[] AND t.state IN ('reserved','submitted','settled')"
            " AND t.reserved_at > %s - make_interval(secs => %s) AND t.reserved_at <= %s",
            (ctx.mandate_id, row["id"], ctx.now, sc["window_seconds"], ctx.now)).fetchone()["s"]
        if spent + amount > sc["window_limit"]:
            return True
    return False


def _hold_reason(ctx: Ctx, g, actor, amount: int, needs_review: bool) -> str | None:
    """Why a request that passed every check is held for the owner instead of reserved (ADR-0008).
    The effective threshold is the LOWEST review_above on the path, so an ancestor's binds descendants.
    The mandate owner is exempt from the threshold (they are the approver) but not from the caller flag."""
    if actor != ctx.mandate["owner_principal_id"]:
        limits = [r["scope"]["review_above"] for r in _path_scopes(ctx, g) if "review_above" in r["scope"]]
        if limits and amount > min(limits):
            return "ABOVE_THRESHOLD"
    return "CALLER_FLAGGED" if needs_review else None


def _insert_tx(ctx: Ctx, g, amount, currency, recipient, category, state, key, phash, *, reason=None,
               proposal=None, ttl=False, review_reason=None):
    expires = ctx.now + timedelta(seconds=RESERVE_TTL_SECONDS) if ttl else None
    return ctx.conn.execute(
        "INSERT INTO transactions(mandate_id, grant_id, amount, currency, recipient, category, state,"
        " reject_reason, idempotency_key, payload_hash, reserve_expires_at, proposal, created_at, updated_at,"
        " reserved_at, review_reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (ctx.mandate_id, g["id"], amount, currency, recipient, category, state, reason, key, phash, expires,
         Jsonb(proposal) if proposal is not None else None, ctx.now, ctx.now,
         ctx.now if state == "reserved" else None, review_reason),
    ).fetchone()


def _decision(tx: dict, replayed: bool = False) -> dict:
    return {"transaction_id": tx["id"], "state": tx["state"], "reason": tx["reject_reason"],
            "review_reason": tx.get("review_reason"), "replayed": replayed}


# --------------------------------------------------------------------------- human review

def review(pool, *, transaction_id, actor, approve: bool) -> dict:
    """Owner decision on a 'proposed' transaction (ADR-0005 section 3). Approval re-runs every
    authorize guard against current state, so a stale proposal cannot reserve funds it no longer could."""
    mid = mandate_of_tx(pool, transaction_id)
    with kernel_tx(pool, mid) as ctx:
        c = ctx.conn
        tx = c.execute("SELECT * FROM transactions WHERE id = %s FOR UPDATE", (transaction_id,)).fetchone()
        if ctx.mandate["owner_principal_id"] != actor:
            raise Forbidden("only the mandate owner may review proposals", code="NOT_OWNER")
        if tx["state"] != "proposed":
            return {**_decision(tx), "replayed": True}
        if not approve:
            reason = "DENIED_BY_REVIEWER"
        else:
            g = c.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (tx["grant_id"],)).fetchone()
            reason = _authorize_problem(ctx, g, tx["amount"], tx["currency"].strip().upper(), tx["recipient"],
                                        tx["category"])
        if reason:
            c.execute("UPDATE transactions SET state = 'rejected', reject_reason = %s, updated_at = %s"
                      " WHERE id = %s AND state = 'proposed'", (reason, ctx.now, tx["id"]))
            audit(c, mid, "TX_REVIEW_REJECTED", actor, tx["id"], reason=reason)
            return {"transaction_id": tx["id"], "state": "rejected", "reason": reason, "replayed": False}
        _reserve(ctx, tx["grant_id"], tx["amount"])
        n = c.execute("UPDATE transactions SET state = 'reserved', reserve_expires_at = %s, updated_at = %s,"
                      " reserved_at = %s WHERE id = %s AND state = 'proposed'",
                      (ctx.now + timedelta(seconds=RESERVE_TTL_SECONDS), ctx.now, ctx.now, tx["id"])).rowcount
        ensure(n == 1, "review: state guard failed")
        movement(c, mid, "reserve", tx["amount"], from_grant=tx["grant_id"], from_bucket="available",
                 to_grant=tx["grant_id"], to_bucket="reserved", transaction_id=tx["id"], actor=actor)
        audit(c, mid, "TX_APPROVED", actor, tx["id"], amount=tx["amount"])
        return {"transaction_id": tx["id"], "state": "reserved", "reason": None, "replayed": False}


# --------------------------------------------------------------------------- transitions

def release(pool, *, transaction_id, actor) -> dict:
    mid = mandate_of_tx(pool, transaction_id)
    with kernel_tx(pool, mid) as ctx:
        tx = ctx.conn.execute("SELECT * FROM transactions WHERE id = %s FOR UPDATE", (transaction_id,)).fetchone()
        _require_manager(ctx, tx["grant_id"], actor)
        if tx["state"] == "released":
            return {"transaction_id": tx["id"], "state": "released", "replayed": True}
        if tx["state"] != "reserved":
            raise Conflict(f"cannot release a {tx['state']} transaction", code=f"RELEASE_FROM_{tx['state'].upper()}")
        release_tx(ctx, tx, from_state="reserved", kind="release", actor=actor)
        return {"transaction_id": tx["id"], "state": "released", "replayed": False}


def _require_settler(ctx: Ctx, actor, *, owner_allowed: bool) -> None:
    """Settlement steps belong to the settlement service. The mandate owner may run the simulated
    path (start/confirm) but can never declare a transfer failed (that would return spent funds)."""
    row = ctx.conn.execute("SELECT kind FROM principals WHERE id = %s", (actor,)).fetchone()
    if row is not None and row["kind"] == "service" and ctx.conn.execute(
            "SELECT 1 FROM mandate_settlers WHERE mandate_id = %s AND principal_id = %s",
            (ctx.mandate["id"], actor)).fetchone():
        return
    if owner_allowed and ctx.mandate["owner_principal_id"] == actor:
        return
    raise Forbidden("not permitted to perform settlement steps", code="NOT_SETTLER")


def bind_settler(pool, *, mandate_id, actor, principal_id) -> dict:
    """Owner-only: authorize a service principal to run settlement steps on THIS mandate (BK-303)."""
    with kernel_tx(pool, mandate_id) as ctx:
        if ctx.mandate["owner_principal_id"] != actor:
            raise Forbidden("only the mandate owner can bind a settler", code="NOT_OWNER")
        row = ctx.conn.execute("SELECT kind FROM principals WHERE id = %s", (principal_id,)).fetchone()
        if row is None or row["kind"] != "service":
            raise ValidationFailed("settler must be a service principal", code="NOT_A_SERVICE")
        n = ctx.conn.execute("INSERT INTO mandate_settlers(mandate_id, principal_id, bound_by) VALUES (%s,%s,%s)"
                             " ON CONFLICT DO NOTHING", (mandate_id, principal_id, actor)).rowcount
        if n:
            audit(ctx.conn, mandate_id, "SETTLER_BOUND", actor, principal_id)
        return {"mandate_id": mandate_id, "principal_id": principal_id, "already": n == 0}


def settle_start(pool, *, transaction_id, actor, on_submit: Callable[[Ctx, dict], None] | None = None) -> dict:
    """reserved -> submitted. Idempotent on submitted/settled. Fails closed if the grant path is dead.

    `on_submit(ctx, tx)` runs INSIDE the same DB transaction, under the mandate lock, after the state
    change. The testnet adapter uses it to sign locally and persist the raw tx (ADR-0007), so a crash
    can never leave a 'submitted' transaction without its signed transfer recorded. It must not do
    network I/O."""
    mid = mandate_of_tx(pool, transaction_id)
    with kernel_tx(pool, mid) as ctx:
        c = ctx.conn
        tx = c.execute("SELECT * FROM transactions WHERE id = %s FOR UPDATE", (transaction_id,)).fetchone()
        _require_settler(ctx, actor, owner_allowed=True)
        if tx["state"] in ("submitted", "settled"):
            return {"transaction_id": tx["id"], "state": tx["state"], "replayed": True}
        if tx["state"] != "reserved":
            raise Conflict(f"cannot settle a {tx['state']} transaction", code=f"SETTLE_FROM_{tx['state'].upper()}")
        g = c.execute("SELECT * FROM grants WHERE id = %s", (tx["grant_id"],)).fetchone()
        problem = _path_problem(ctx, g)
        if problem:
            raise Conflict("grant path is not active", code=problem)
        n = c.execute(
            "UPDATE transactions SET state = 'submitted', updated_at = %s WHERE id = %s AND state = 'reserved'"
            " AND reserve_expires_at > %s", (ctx.now, tx["id"], ctx.now)).rowcount
        if n != 1:
            raise Conflict("reservation expired", code="RESERVATION_EXPIRED")
        if on_submit is not None:
            on_submit(ctx, {**tx, "state": "submitted"})
        audit(c, mid, "TX_SUBMITTED", actor, tx["id"])
        return {"transaction_id": tx["id"], "state": "submitted", "replayed": False}


def settle_confirm(pool, *, transaction_id, actor) -> dict:
    """submitted -> settled: reserved -> settled on the grant that reserved (even if revoked since)."""
    mid = mandate_of_tx(pool, transaction_id)
    with kernel_tx(pool, mid) as ctx:
        c = ctx.conn
        tx = c.execute("SELECT * FROM transactions WHERE id = %s FOR UPDATE", (transaction_id,)).fetchone()
        _require_settler(ctx, actor, owner_allowed=True)
        if tx["state"] == "settled":
            return {"transaction_id": tx["id"], "state": "settled", "replayed": True}
        if tx["state"] != "submitted":
            raise Conflict(f"cannot confirm a {tx['state']} transaction", code=f"CONFIRM_FROM_{tx['state'].upper()}")
        n = c.execute("UPDATE transactions SET state = 'settled', updated_at = %s WHERE id = %s AND state = 'submitted'",
                      (ctx.now, tx["id"])).rowcount
        ensure(n == 1, "settle_confirm: state guard failed")
        n = c.execute(
            "UPDATE grants SET reserved = reserved - %s, settled = settled + %s WHERE id = %s AND reserved >= %s",
            (tx["amount"], tx["amount"], tx["grant_id"], tx["amount"])).rowcount
        ensure(n == 1, "settle_confirm: reserved underflow")
        movement(c, mid, "settle", tx["amount"], from_grant=tx["grant_id"], from_bucket="reserved",
                 to_grant=tx["grant_id"], to_bucket="settled", transaction_id=tx["id"], actor=actor)
        audit(c, mid, "TX_SETTLED", actor, tx["id"], amount=tx["amount"])
        return {"transaction_id": tx["id"], "state": "settled", "replayed": False}


def settle_fail(pool, *, transaction_id, actor, proof: str) -> dict:
    """submitted -> released, only on proven failure (ADR-0007), only by the settlement service.
    `proof` (e.g. a reverted receipt's tx hash) is recorded in the audit trail."""
    if not isinstance(proof, str) or not proof.strip():
        raise ValidationFailed("a failure proof is required", code="PROOF_REQUIRED")
    mid = mandate_of_tx(pool, transaction_id)
    with kernel_tx(pool, mid) as ctx:
        tx = ctx.conn.execute("SELECT * FROM transactions WHERE id = %s FOR UPDATE", (transaction_id,)).fetchone()
        _require_settler(ctx, actor, owner_allowed=False)
        if tx["state"] == "released":
            return {"transaction_id": tx["id"], "state": "released", "replayed": True}
        if tx["state"] != "submitted":
            raise Conflict(f"cannot fail a {tx['state']} transaction", code=f"FAIL_FROM_{tx['state'].upper()}")
        release_tx(ctx, tx, from_state="submitted", kind="settle_failed", actor=actor)
        audit(ctx.conn, mid, "TX_SETTLE_FAILED", actor, tx["id"], proof=proof[:500])
        return {"transaction_id": tx["id"], "state": "released", "replayed": False}


# --------------------------------------------------------------------------- revoke

def revoke(pool, *, grant_id, actor) -> dict:
    mid = mandate_of_grant(pool, grant_id)
    with kernel_tx(pool, mid) as ctx:
        g = ctx.conn.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (grant_id,)).fetchone()
        _require_manager(ctx, grant_id, actor, allow_self=False)
        if g["status"] != "active":
            return {"grant_id": g["id"], "status": g["status"], "already": True}
        return {**reclaim_subtree(ctx, g, "revoked", actor=actor), "already": False}


def _require_manager(ctx: Ctx, grant_id, actor, allow_self: bool = True) -> None:
    """Mandate owner, or holder of a strict ancestor (and the holder itself when allow_self)."""
    if ctx.mandate["owner_principal_id"] == actor:
        return
    g = ctx.conn.execute("SELECT path FROM grants WHERE id = %s", (grant_id,)).fetchone()
    ids = g["path"] if allow_self else g["path"][:-1]
    if ids:
        holders = {r["holder_principal_id"] for r in ctx.conn.execute(
            "SELECT holder_principal_id FROM grants WHERE id = ANY(%s)", (ids,))}
        if actor in holders:
            return
    raise Forbidden("not permitted to manage this grant", code="NOT_PERMITTED")
