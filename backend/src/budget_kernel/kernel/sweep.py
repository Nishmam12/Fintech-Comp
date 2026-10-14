"""Lazy, lock-scoped sweep (ADR-0005 section 5). Runs at the start of every kernel op.

1. Expire grants whose expires_at has passed (reclaiming their subtree).
2. Release 'reserved' transactions past their TTL. Never touches 'submitted' (reconciler only).
"""
from __future__ import annotations

from .funds import reclaim_subtree, release_tx
from .tx import Ctx


def sweep(ctx: Ctx) -> None:
    c, mid = ctx.conn, ctx.mandate_id
    due = c.execute(
        "SELECT * FROM grants WHERE mandate_id = %s AND status = 'active' AND expires_at <= now()"
        " ORDER BY depth", (mid,)).fetchall()
    for g in due:
        cur = c.execute("SELECT status FROM grants WHERE id = %s", (g["id"],)).fetchone()
        if cur["status"] == "active":  # may already have been covered as a descendant
            reclaim_subtree(ctx, g, "expired")
    stale = c.execute(
        "SELECT * FROM transactions WHERE mandate_id = %s AND state = 'reserved' AND reserve_expires_at <= now()",
        (mid,)).fetchall()
    for tx in stale:
        release_tx(ctx, tx, from_state="reserved", kind="ttl_release")
