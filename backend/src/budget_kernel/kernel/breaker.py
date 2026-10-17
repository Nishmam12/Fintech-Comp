"""Agent circuit breaker (ADR-0009 part B).

A grant holder that keeps asking for things its grant forbids is probing. Each such refusal (and each suspected
prompt injection) is a weighted strike; enough strikes inside the window suspend the grant, and a suspended
grant (with its whole subtree) cannot authorize, delegate, start settlement or be approved until the owner
or an ancestor holder reinstates it. The breaker only ever makes the kernel stricter: it never authorizes.

Every function here runs under the mandate lock (kernel_tx) so strike counting and the status change are one
atomic step: two racing refusals at the limit suspend the grant exactly once.
"""
from __future__ import annotations

import os

from .errors import Conflict, Forbidden, ValidationFailed
from .tx import Ctx, audit, kernel_tx, mandate_of_grant

STRIKE_LIMIT = int(os.environ.get("BK_STRIKE_LIMIT", "5"))
STRIKE_WINDOW_SECONDS = int(os.environ.get("BK_STRIKE_WINDOW_SECONDS", "600"))
REFUSAL_WEIGHT = 1
INJECTION_WEIGHT = 3
# Refusals that look like probing the grant's limits. Path refusals (revoked, expired, frozen, suspended) are
# deliberately absent: an owner revoking a parent must not turn innocent children into suspects.
PROBING_REASONS = frozenset({
    "CATEGORY_NOT_ALLOWED", "RECIPIENT_NOT_ALLOWED", "PER_TX_LIMIT_EXCEEDED", "VELOCITY_LIMIT_EXCEEDED",
    "INSUFFICIENT_FUNDS", "CURRENCY_MISMATCH", "TOO_MANY_PENDING_REVIEWS",
})


def _strikes_in_window(ctx: Ctx, grant_id, reinstated_at) -> int:
    return ctx.conn.execute(
        "SELECT coalesce(sum(weight), 0)::int AS n FROM grant_strikes WHERE grant_id = %s"
        " AND created_at > %s - make_interval(secs => %s) AND (%s::timestamptz IS NULL OR created_at > %s)",
        (grant_id, ctx.now, STRIKE_WINDOW_SECONDS, reinstated_at, reinstated_at)).fetchone()["n"]


def add_strike(ctx: Ctx, g: dict, actor, kind: str, reason: str, weight: int) -> tuple[int, bool]:
    """Record a strike for the grant holder `actor` and suspend the grant if the window total reaches the limit.
    Returns (strikes_in_window, suspended_by_this_call). The mandate owner is exempt: they are the approver,
    and suspending the owner's own root grant would only lock the owner out. Callers must have checked that
    `actor` is the grant's holder, so an outsider can never add a strike to someone else's grant."""
    if actor == ctx.mandate["owner_principal_id"]:
        return 0, False
    c = ctx.conn
    c.execute("INSERT INTO grant_strikes(mandate_id, grant_id, actor_principal_id, kind, reason, weight, created_at)"
              " VALUES (%s,%s,%s,%s,%s,%s,%s)", (ctx.mandate_id, g["id"], actor, kind, reason[:200], weight, ctx.now))
    total = _strikes_in_window(ctx, g["id"], g["reinstated_at"])
    tripped = False
    if total >= STRIKE_LIMIT:
        tripped = c.execute(
            "UPDATE grants SET status = 'suspended', suspended_at = %s, suspend_reason = 'STRIKES'"
            " WHERE id = %s AND status = 'active'", (ctx.now, g["id"])).rowcount == 1
        if tripped:
            audit(c, ctx.mandate_id, "GRANT_SUSPENDED", actor, g["id"], reason="STRIKES", strikes=total,
                  window_seconds=STRIKE_WINDOW_SECONDS)
    return total, tripped


def record_signal(pool, *, grant_id, actor, kind: str, reason: str) -> dict:
    """Record an INJECTION strike against the holder's grant (called by the API when a request looks like a
    prompt injection). Returns {grant_id, strikes, suspended}; `suspended` is the grant's state afterwards."""
    if kind != "INJECTION":
        raise ValidationFailed("unknown signal kind", code="BAD_SIGNAL")
    reason = (str(reason).strip() or "INJECTION_SUSPECTED")
    mid = mandate_of_grant(pool, grant_id)
    with kernel_tx(pool, mid) as ctx:
        g = ctx.conn.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (grant_id,)).fetchone()
        if g["holder_principal_id"] != actor:
            raise Forbidden("only the grant holder can be signalled", code="NOT_GRANT_HOLDER")
        total, _ = add_strike(ctx, g, actor, "INJECTION", reason, INJECTION_WEIGHT)
        status = ctx.conn.execute("SELECT status FROM grants WHERE id = %s", (grant_id,)).fetchone()["status"]
        return {"grant_id": g["id"], "strikes": total, "suspended": status == "suspended"}


def suspend(pool, *, grant_id, actor) -> dict:
    """Manual suspend by the mandate owner or a holder of a strict ancestor (the same rule as revoke).
    Idempotent. Returns {grant_id, status, already}."""
    from .ops import _require_manager
    mid = mandate_of_grant(pool, grant_id)
    with kernel_tx(pool, mid) as ctx:
        g = ctx.conn.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (grant_id,)).fetchone()
        _require_manager(ctx, grant_id, actor, allow_self=False)
        if g["status"] == "suspended":
            return {"grant_id": g["id"], "status": "suspended", "already": True}
        if g["status"] != "active":
            raise Conflict(f"cannot suspend a {g['status']} grant", code=f"GRANT_{g['status'].upper()}")
        ctx.conn.execute("UPDATE grants SET status = 'suspended', suspended_at = %s, suspend_reason = 'MANUAL'"
                         " WHERE id = %s AND status = 'active'", (ctx.now, g["id"]))
        audit(ctx.conn, mid, "GRANT_SUSPENDED", actor, g["id"], reason="MANUAL")
        return {"grant_id": g["id"], "status": "suspended", "already": False}


def reinstate(pool, *, grant_id, actor) -> dict:
    """suspended -> active, MANDATE OWNER ONLY (ADR-0009 amendment K1): reinstating loosens, so an agent (or a
    colluding ancestor holder) must never be able to undo a suspension it earned. Strikes before `reinstated_at`
    no longer count, so the grant starts again with a clean slate. Returns {grant_id, status}."""
    mid = mandate_of_grant(pool, grant_id)
    with kernel_tx(pool, mid) as ctx:
        g = ctx.conn.execute("SELECT * FROM grants WHERE id = %s FOR UPDATE", (grant_id,)).fetchone()
        if ctx.mandate["owner_principal_id"] != actor:
            raise Forbidden("only the mandate owner may reinstate a suspended grant", code="NOT_OWNER")
        if g["status"] != "suspended":
            raise Conflict("the grant is not suspended", code="NOT_SUSPENDED")
        ctx.conn.execute("UPDATE grants SET status = 'active', suspended_at = NULL, suspend_reason = NULL,"
                         " reinstated_at = %s WHERE id = %s AND status = 'suspended'", (ctx.now, g["id"]))
        audit(ctx.conn, mid, "GRANT_REINSTATED", actor, g["id"])
        return {"grant_id": g["id"], "status": "active"}
