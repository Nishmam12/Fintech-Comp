"""On-chain anchor of the hash-chain heads (ADR-0009 A5, BK-401). Evidence only: an anchor never authorizes anything
and the kernel never reads chain state. Same persist-then-broadcast discipline and nonce allocator as payments."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .adapter import PENDING, SettlementConfig, SettlementRefused, drive, ensure_account
from .signer import Signer

MAGIC = b"BKANCHOR1"


def snapshot(pool) -> list[tuple[str, int, str]]:
    """Every chain head with seq > 0, sorted bytewise by chain_key, from one REPEATABLE READ snapshot."""
    with pool.connection() as c:
        with c.transaction():
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            rows = c.execute("SELECT chain_key, seq, head_hash FROM chain_heads WHERE seq > 0").fetchall()
    return sorted(((r["chain_key"], r["seq"], r["head_hash"]) for r in rows), key=lambda t: t[0].encode())


def digest_of(heads: list[tuple[str, int, str]]) -> str:
    return hashlib.sha256("".join(f"{k}|{s}|{h}\n" for k, s, h in heads).encode()).hexdigest()


def create(pool, *, chain, signer: Signer, cfg: SettlementConfig, now=None) -> dict:
    """Snapshot the heads, sign a self-transfer carrying the digest, persist it with its nonce, then broadcast."""
    ensure_account(pool, chain, signer.address, cfg.chain_id)
    fees = chain.fees()
    if fees[0] > cfg.max_fee_ceiling:
        raise SettlementRefused("gas price above ceiling; retry later")
    heads = snapshot(pool)
    if not heads:
        raise SettlementRefused("nothing to anchor")
    digest = digest_of(heads)
    with pool.connection() as c:
        with c.transaction():                         # nonce + signed bytes + heads commit together or not at all
            row = c.execute("UPDATE settlement_accounts SET next_nonce = next_nonce + 1 WHERE chain_id=%s AND address=%s"
                            " RETURNING next_nonce - 1 AS nonce", (cfg.chain_id, signer.address)).fetchone()
            if row is None:
                raise SettlementRefused("settlement account not initialised")
            raw, h = signer.sign_anchor(chain_id=cfg.chain_id, nonce=row["nonce"], data=MAGIC + bytes.fromhex(digest),
                                        max_fee=fees[0], priority_fee=fees[1])
            aid = c.execute("INSERT INTO anchors(chain_id, from_address, nonce, digest, raw_tx, tx_hash, status)"
                            " VALUES (%s,%s,%s,%s,%s,%s,'signed') RETURNING id",
                            (cfg.chain_id, signer.address, row["nonce"], digest, raw, h)).fetchone()["id"]
            c.cursor().executemany("INSERT INTO anchor_heads(anchor_id, chain_key, seq, head_hash) VALUES (%s,%s,%s,%s)",
                                   [(aid, k, s, hh) for k, s, hh in heads])
    out = advance(pool, anchor_id=aid, chain=chain, cfg=cfg, now=now)
    return {**out, "digest": digest, "chains": len(heads)}


def advance(pool, *, anchor_id, chain, cfg: SettlementConfig, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    with pool.connection() as c:
        row = c.execute("SELECT * FROM anchors WHERE id = %s", (anchor_id,)).fetchone()
    if row is None:
        raise SettlementRefused("no such anchor")
    out = {"anchor_id": anchor_id, "tx_hash": row["tx_hash"], "status": row["status"],
           "explorer_url": cfg.explorer_url(row["tx_hash"])}
    return drive(pool, "anchors", "id", row, out, chain=chain, cfg=cfg, now=now,
                 confirm=lambda: None, fail=lambda proof: None, done_cols={})


def reconcile(pool, *, chain, cfg: SettlementConfig, now=None) -> list[dict]:
    with pool.connection() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM anchors WHERE status = ANY(%s) ORDER BY id", (list(PENDING),))]
    return [advance(pool, anchor_id=i, chain=chain, cfg=cfg, now=now) for i in ids]
