"""Lazy, lock-scoped sweep (ADR-0005 section 5). Runs at the start of every kernel op.

1. Expire grants whose expires_at has passed (reclaiming their subtree). The root grant shares the
   mandate's expiry, so an expired mandate freezes with its funds stranded (still counted by I1).
2. Release 'reserved' transactions past their TTL. Never touches 'submitted' (reconciler only).
3. Reject 'proposed' transactions nobody reviewed within PROPOSAL_TTL_SECONDS (they hold no funds).
"""
from __future__ import annotations

from datetime import timedelta

from . import tx as txmod
from .funds import reclaim_subtree, release_tx
from .tx import Ctx, audit


def sweep(ctx: Ctx) -> dict:
    c, mid, now = ctx.conn, ctx.mandate_id, ctx.now
    done = {"expired_grants": 0, "released": 0, "review_expired": 0}
    due = c.execute(
        "SELECT * FROM grants WHERE mandate_id = %s AND status IN ('active', 'suspended') AND expires_at <= %s ORDER BY depth",
        (mid, now)).fetchall()
    for g in due:
        cur = c.execute("SELECT status FROM grants WHERE id = %s", (g["id"],)).fetchone()
        if cur["status"] in ("active", "suspended"):  # may already have been covered as a descendant
            reclaim_subtree(ctx, g, "expired")
            done["expired_grants"] += 1
    stale = c.execute(
        "SELECT * FROM transactions WHERE mandate_id = %s AND state = 'reserved' AND reserve_expires_at <= %s",
        (mid, now)).fetchall()
    for tx in stale:
        release_tx(ctx, tx, from_state="reserved", kind="ttl_release")
        done["released"] += 1
    cutoff = now - timedelta(seconds=txmod.PROPOSAL_TTL_SECONDS)
    for tx in c.execute(
        "UPDATE transactions SET state = 'rejected', reject_reason = 'REVIEW_EXPIRED', updated_at = %s"
        " WHERE mandate_id = %s AND state = 'proposed' AND created_at <= %s RETURNING id",
        (now, mid, cutoff)).fetchall():
        audit(c, mid, "TX_REVIEW_EXPIRED", None, tx["id"])
        done["review_expired"] += 1
    return done
