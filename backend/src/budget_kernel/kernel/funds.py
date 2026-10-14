"""Fund movements shared by release, revoke, expiry and sweep (ADR-0004 movement table).

Callers must already hold the mandate lock (use kernel_tx). Nothing here opens a transaction.
"""
from __future__ import annotations

from .tx import Ctx, audit, movement


def release_target(ctx: Ctx, grant: dict):
    """Nearest active, unexpired grant on grant.path (self if active); else the root (stranded)."""
    rows = ctx.conn.execute(
        "SELECT id, (status = 'active' AND expires_at > now()) AS live FROM grants WHERE id = ANY(%s)",
        (grant["path"],),
    ).fetchall()
    live = {r["id"]: r["live"] for r in rows}
    for gid in reversed(grant["path"]):
        if live.get(gid):
            return gid
    return grant["path"][0]


def release_tx(ctx: Ctx, tx: dict, *, from_state: str, kind: str, actor=None) -> None:
    """reserved/submitted -> released: reserved -= amt on its grant, +amt on the release target."""
    c = ctx.conn
    n = c.execute(
        "UPDATE transactions SET state = 'released', updated_at = now() WHERE id = %s AND state = %s",
        (tx["id"], from_state),
    ).rowcount
    assert n == 1, "release_tx: state guard failed"
    grant = c.execute("SELECT * FROM grants WHERE id = %s", (tx["grant_id"],)).fetchone()
    target = release_target(ctx, grant)
    n = c.execute(
        "UPDATE grants SET reserved = reserved - %s WHERE id = %s AND reserved >= %s",
        (tx["amount"], grant["id"], tx["amount"]),
    ).rowcount
    assert n == 1, "release_tx: reserved underflow"
    c.execute("UPDATE grants SET available = available + %s WHERE id = %s", (tx["amount"], target))
    movement(c, ctx.mandate_id, kind, tx["amount"], from_grant=grant["id"], from_bucket="reserved",
             to_grant=target, to_bucket="available", transaction_id=tx["id"], actor=actor)
    audit(c, ctx.mandate_id, "TX_RELEASED", actor, tx["id"], reason=kind, to_grant=str(target))


def reclaim_subtree(ctx: Ctx, grant: dict, new_status: str, *, actor=None) -> dict:
    """Revoke/expire `grant` and its whole subtree (ADR-0005 section 6, steps 1-6)."""
    assert new_status in ("revoked", "expired")
    c, mid = ctx.conn, ctx.mandate_id
    sub = c.execute("SELECT * FROM grants WHERE mandate_id = %s AND %s = ANY(path)", (mid, grant["id"])).fetchall()
    sub_ids = [g["id"] for g in sub]
    c.execute(
        "UPDATE grants SET status = %s, revoked_at = now() WHERE id = ANY(%s) AND status = 'active'",
        (new_status, sub_ids),
    )
    # Strict ancestors, nearest first; the first live one receives the funds.
    anc = grant["path"][:-1]
    target = None
    if anc:
        live = {r["id"] for r in c.execute(
            "SELECT id FROM grants WHERE id = ANY(%s) AND status = 'active' AND expires_at > now()", (anc,))}
        target = next((a for a in reversed(anc) if a in live), None)
    stranded = target is None
    if stranded:
        target = grant["path"][0]
        c.execute("UPDATE mandates SET status = 'frozen' WHERE id = %s", (mid,))

    # Release reservations in the subtree; 'submitted' transfers cannot be recalled (in flight).
    reserved_txs = c.execute(
        "SELECT * FROM transactions WHERE grant_id = ANY(%s) AND state = 'reserved'", (sub_ids,)).fetchall()
    released_total = 0
    for tx in reserved_txs:
        n = c.execute("UPDATE transactions SET state = 'released', updated_at = now()"
                      " WHERE id = %s AND state = 'reserved'", (tx["id"],)).rowcount
        assert n == 1
        n = c.execute("UPDATE grants SET reserved = reserved - %s WHERE id = %s AND reserved >= %s",
                      (tx["amount"], tx["grant_id"], tx["amount"])).rowcount
        assert n == 1
        released_total += tx["amount"]
        movement(c, mid, "reclaim_reservation", tx["amount"], from_grant=tx["grant_id"], from_bucket="reserved",
                 to_grant=target, to_bucket="available", transaction_id=tx["id"], actor=actor)

    available_total = 0
    for g in c.execute("SELECT id, available FROM grants WHERE id = ANY(%s) AND available > 0", (sub_ids,)).fetchall():
        available_total += g["available"]
        if g["id"] != target:
            movement(c, mid, "reclaim_available", g["available"], from_grant=g["id"], from_bucket="available",
                     to_grant=target, to_bucket="available", actor=actor)
    c.execute("UPDATE grants SET available = 0 WHERE id = ANY(%s) AND available > 0", (sub_ids,))
    moved = available_total + released_total
    if moved:
        c.execute("UPDATE grants SET available = available + %s WHERE id = %s", (moved, target))

    inflight = c.execute(
        "SELECT count(*) AS n, coalesce(sum(amount), 0)::bigint AS amt FROM transactions"
        " WHERE grant_id = ANY(%s) AND state = 'submitted'", (sub_ids,)).fetchone()
    result = {
        "grant_id": grant["id"], "status": new_status, "reclaimed": moved, "target_grant_id": target,
        "stranded_on_root": stranded, "released_reservations": len(reserved_txs),
        "in_flight_count": inflight["n"], "in_flight_amount": inflight["amt"],
    }
    audit(c, mid, "GRANT_REVOKED" if new_status == "revoked" else "GRANT_EXPIRED", actor, grant["id"],
          **{k: str(v) if hasattr(v, "hex") else v for k, v in result.items()})
    return result
