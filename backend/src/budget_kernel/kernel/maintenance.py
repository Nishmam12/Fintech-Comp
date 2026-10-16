"""Housekeeping for the background worker (ADR-0009 B5). Authorizes nothing: it only runs the lazy sweep
(expiry, reservation TTL, review TTL) for mandates that are due, instead of waiting for the next request."""
from __future__ import annotations

from .tx import kernel_tx


def tick(pool, mandate_id) -> dict:
    """Run the sweep for one mandate under its lock and report what it did."""
    with kernel_tx(pool, mandate_id) as ctx:
        return {"mandate_id": str(mandate_id), **ctx.swept}


def due_mandates(pool, limit: int = 50) -> list:
    """Mandates with sweepable state: an active or suspended grant past its expiry, a reservation past its TTL,
    or a proposal past its review TTL. Read-only, no lock; the tick re-checks everything under the lock."""
    from .tx import PROPOSAL_TTL_SECONDS
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT mandate_id FROM ("
            " SELECT mandate_id FROM grants WHERE status IN ('active', 'suspended') AND expires_at <= clock_timestamp()"
            " UNION SELECT mandate_id FROM transactions WHERE state = 'reserved' AND reserve_expires_at <= clock_timestamp()"
            " UNION SELECT mandate_id FROM transactions WHERE state = 'proposed'"
            "   AND created_at <= clock_timestamp() - make_interval(secs => %s)"
            ") d LIMIT %s", (PROPOSAL_TTL_SECONDS, int(limit))).fetchall()
    return [r["mandate_id"] for r in rows]
