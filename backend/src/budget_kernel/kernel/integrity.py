"""Hash-chain verifier (ADR-0009 part A4).

Recomputes every row hash of a mandate's chain from raw column values, independently of the SQL trigger that
wrote them, and checks sequence, links, the stored head and the newest confirmed on-chain anchor.

Read-only: one REPEATABLE READ READ ONLY transaction (head and rows come from the same snapshot) and no mandate
lock, so verifying never blocks or is blocked by money operations. The whole chain is read into memory, which
is fine for the sizes this system handles; an external auditor can run the same code on exported rows.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .errors import NotFound

ZERO = "0" * 64
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _f(v: Any) -> str:
    """Field encoding: NULL -> '', uuid/int/text -> their text, timestamptz -> integer microseconds since the
    Unix epoch (UTC); then length-prefixed so no field can bleed into its neighbour."""
    if v is None:
        s = ""
    elif isinstance(v, datetime):
        d = v.astimezone(timezone.utc) - _EPOCH
        s = str((d.days * 86_400 + d.seconds) * 1_000_000 + d.microseconds)
    else:
        s = str(v)
    return f"{len(s)}:{s}"


def canon_audit(r: dict) -> str:
    cols = (r["id"], r["chain_key"], r["seq"], r["mandate_id"], r["kind"], r["actor_principal_id"],
            r["subject_id"], r["created_at"], r["detail_text"])
    return "A|" + "|".join(_f(c) for c in cols)


def canon_movement(r: dict) -> str:
    cols = (r["id"], r["chain_key"], r["seq"], r["mandate_id"], r["kind"], r["amount"], r["from_grant_id"],
            r["from_bucket"], r["to_grant_id"], r["to_bucket"], r["transaction_id"], r["actor_principal_id"],
            r["created_at"])
    return "M|" + "|".join(_f(c) for c in cols)


def row_hash(prev_hash: str, canon: str) -> str:
    return hashlib.sha256(f"BK1|{prev_hash}|{canon}".encode("utf-8")).hexdigest()


def check_chain(rows: list[dict], head: dict | None) -> tuple[str | None, int | None]:
    """Pure check of already-fetched rows (each tagged with `_table`), ordered by seq.
    Returns (reason, broken_at); (None, None) when the chain is intact. First failure wins, in the order
    SEQ_GAP, PREV_MISMATCH, HASH_MISMATCH (per row), then HEAD_MISMATCH."""
    prev = ZERO
    for i, r in enumerate(rows, start=1):
        if r["seq"] != i:
            return "SEQ_GAP", i
        if r["prev_hash"] != prev:
            return "PREV_MISMATCH", i
        canon = canon_audit(r) if r["_table"] == "audit_events" else canon_movement(r)
        if row_hash(r["prev_hash"], canon) != r["row_hash"]:
            return "HASH_MISMATCH", i
        prev = r["row_hash"]
    n = len(rows)
    if head is None:
        return (None, None) if n == 0 else ("HEAD_MISMATCH", None)
    if head["seq"] != n or head["head_hash"] != (prev if n else ZERO):
        return "HEAD_MISMATCH", None
    return None, None


def verify(pool, mandate_id) -> dict:
    key = f"mandate:{mandate_id}"
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            if conn.execute("SELECT 1 FROM mandates WHERE id = %s", (mandate_id,)).fetchone() is None:
                raise NotFound("mandate not found", code="MANDATE_NOT_FOUND")
            rows = conn.execute(
                "SELECT 'audit_events' AS _table, id, chain_key, seq, mandate_id, kind, actor_principal_id, subject_id,"
                " created_at, detail::text AS detail_text, NULL::bigint AS amount, NULL::uuid AS from_grant_id,"
                " NULL::text AS from_bucket, NULL::uuid AS to_grant_id, NULL::text AS to_bucket,"
                " NULL::uuid AS transaction_id, prev_hash, row_hash FROM audit_events WHERE chain_key = %s"
                " UNION ALL "
                "SELECT 'ledger_movements', id, chain_key, seq, mandate_id, kind, actor_principal_id, NULL::uuid,"
                " created_at, NULL::text, amount, from_grant_id, from_bucket, to_grant_id, to_bucket, transaction_id,"
                " prev_hash, row_hash FROM ledger_movements WHERE chain_key = %s ORDER BY seq",
                (key, key)).fetchall()
            head = conn.execute("SELECT seq, head_hash FROM chain_heads WHERE chain_key = %s", (key,)).fetchone()
            anchor = _newest_anchor(conn, key)
            confirmed = _newest_anchor(conn, key, confirmed_only=True)
            now = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
    reason, broken_at = check_chain(rows, head)
    by_seq = {r["seq"]: r["row_hash"] for r in rows}

    def matches(a: dict) -> bool:
        return by_seq.get(a["seq"]) == a["head_hash"]

    if reason is None and confirmed is not None and not matches(confirmed):
        reason, broken_at = "ANCHOR_MISMATCH", confirmed["seq"]
    last_anchor = None
    if anchor is not None:
        last_anchor = {"anchor_id": anchor["anchor_id"], "seq": anchor["seq"], "head_hash": anchor["head_hash"],
                       "tx_hash": anchor["tx_hash"], "status": anchor["status"], "matches": matches(anchor)}
    return {"mandate_id": str(mandate_id), "chain_key": key, "ok": reason is None, "length": len(rows),
            "head_seq": head["seq"] if head else 0, "head_hash": head["head_hash"] if head else ZERO,
            "broken_at": broken_at, "reason": reason, "verified_at": now.isoformat(), "last_anchor": last_anchor}


def _newest_anchor(conn, chain_key: str, confirmed_only: bool = False) -> dict | None:
    """Newest anchor covering this chain, or None. The anchor tables arrive with migration 007 (BK-401);
    until they exist there is nothing to check."""
    if conn.execute("SELECT to_regclass('anchor_heads') AS t").fetchone()["t"] is None:
        return None
    return conn.execute(
        "SELECT a.id AS anchor_id, h.seq, h.head_hash, a.tx_hash, a.status FROM anchor_heads h"
        " JOIN anchors a ON a.id = h.anchor_id WHERE h.chain_key = %s" + (" AND a.status = 'confirmed'" if confirmed_only else "") +
        " ORDER BY a.id DESC LIMIT 1", (chain_key,)).fetchone()
