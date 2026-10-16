"""Settlement adapter (ADR-0007). Never authorizes: it signs only inside kernel.settle_start's on_submit hook,
from the DB transaction row, and only for a static recipient registry. No caller input reaches the transfer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .. import kernel
from .chain import ChainError
from .signer import Signer

ALLOWED_CHAIN_IDS = frozenset({84532})  # Base Sepolia only; mainnet ids (1, 8453) are refused by construction
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
PENDING = ("signed", "broadcast", "stuck")


class SettlementRefused(Exception):
    """Raised inside on_submit so the whole settle_start rolls back: the tx stays 'reserved', no nonce consumed."""


@dataclass(frozen=True)
class SettlementConfig:
    recipients: dict[str, str]                       # kernel recipient name -> address (operator-controlled)
    chain_id: int = 84532
    token: str = USDC_BASE_SEPOLIA
    rates: dict[str, int] = field(default_factory=lambda: {"USD": 10_000})   # minor unit -> 6-decimal USDC base units
    confirmations: int = 2
    max_fee_ceiling: int = 50 * 10**9                # wei/gas; above this we wait, never re-sign
    nonce_gone_wait: timedelta = timedelta(seconds=60)
    stuck_after: timedelta = timedelta(minutes=30)
    explorer: str = "https://sepolia-explorer.base.org/tx/"

    def __post_init__(self):
        if self.chain_id not in ALLOWED_CHAIN_IDS:
            raise SettlementRefused(f"chain {self.chain_id} is not allowed")

    def explorer_url(self, tx_hash: str) -> str:
        return self.explorer + tx_hash


def ensure_account(pool, chain, address: str, chain_id: int) -> None:
    """Seed the nonce counter (network call, so outside any lock). Only seeds when no row exists."""
    with pool.connection() as c:
        if c.execute("SELECT 1 FROM settlement_accounts WHERE chain_id=%s AND address=%s", (chain_id, address)).fetchone():
            return
    n = chain.nonce(address, "pending")
    with pool.connection() as c:
        c.execute("INSERT INTO settlement_accounts(chain_id, address, next_nonce) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                  (chain_id, address, n))


def _sign_in_tx(ctx, tx: dict, *, signer: Signer, cfg: SettlementConfig, fees: tuple[int, int]) -> None:
    """Runs under the mandate lock inside settle_start: no network I/O."""
    to = cfg.recipients.get(tx["recipient"])
    rate = cfg.rates.get(tx["currency"].strip())
    if to is None:
        raise SettlementRefused("recipient has no registered address")
    if rate is None:
        raise SettlementRefused("currency has no token mapping")
    if fees[0] > cfg.max_fee_ceiling:
        raise SettlementRefused("gas price above ceiling; retry later")
    amount = int(tx["amount"]) * rate
    row = ctx.conn.execute("UPDATE settlement_accounts SET next_nonce = next_nonce + 1 WHERE chain_id=%s AND address=%s"
                           " RETURNING next_nonce - 1 AS nonce", (cfg.chain_id, signer.address)).fetchone()
    if row is None:
        raise SettlementRefused("settlement account not initialised")
    raw, h = signer.sign_transfer(chain_id=cfg.chain_id, nonce=row["nonce"], token=cfg.token, to=to, amount=amount,
                                  max_fee=fees[0], priority_fee=fees[1])
    ctx.conn.execute(
        "INSERT INTO chain_settlements(transaction_id, chain_id, from_address, nonce, to_address, token_address,"
        " token_amount, raw_tx, tx_hash, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'signed')",
        (tx["id"], cfg.chain_id, signer.address, row["nonce"], to, cfg.token, amount, raw, h))


def settle(pool, *, transaction_id, actor, chain, signer: Signer, cfg: SettlementConfig, now=None) -> dict:
    """Kernel-authorized transfer: settle_start (signs+persists atomically), then broadcast and confirm.
    Safe to call repeatedly: a replay never signs again, it just advances the existing transfer."""
    ensure_account(pool, chain, signer.address, cfg.chain_id)
    fees = chain.fees()
    kernel.settle_start(pool, transaction_id=transaction_id, actor=actor,
                        on_submit=lambda ctx, tx: _sign_in_tx(ctx, tx, signer=signer, cfg=cfg, fees=fees))
    return advance(pool, transaction_id=transaction_id, actor=actor, chain=chain, cfg=cfg, now=now)


def _update_row(pool, table: str, key: str, row_id, **cols) -> None:
    sets = ", ".join(f"{k} = %s" for k in cols)
    with pool.connection() as c:
        c.execute(f"UPDATE {table} SET {sets}, updated_at = now() WHERE {key} = %s", (*cols.values(), row_id))


def _update(pool, tx_id, **cols) -> None:
    _update_row(pool, "chain_settlements", "transaction_id", tx_id, **cols)


def advance(pool, *, transaction_id, actor, chain, cfg: SettlementConfig, now=None) -> dict:
    """Move one transfer forward: broadcast the SAME stored bytes, then confirm/fail on proof. Idempotent."""
    now = now or datetime.now(timezone.utc)
    with pool.connection() as c:
        row = c.execute("SELECT * FROM chain_settlements WHERE transaction_id = %s", (transaction_id,)).fetchone()
    if row is None:
        raise SettlementRefused("no signed transfer for this transaction")
    out = {"transaction_id": transaction_id, "tx_hash": row["tx_hash"], "status": row["status"],
           "explorer_url": cfg.explorer_url(row["tx_hash"])}
    return drive(pool, "chain_settlements", "transaction_id", row, out, chain=chain, cfg=cfg, now=now,
                 confirm=lambda: kernel.settle_confirm(pool, transaction_id=transaction_id, actor=actor),
                 fail=lambda proof: kernel.settle_fail(pool, transaction_id=transaction_id, actor=actor, proof=proof),
                 done_cols={"confirmed_at": now})


def drive(pool, table: str, key: str, row, out: dict, *, chain, cfg: SettlementConfig, now, confirm, fail,
          done_cols: dict) -> dict:
    """The persist-then-broadcast state machine shared by payments and anchors (BK-401). `confirm()` / `fail(proof)`
    run the table's own side effect (kernel calls for a payment, nothing for an anchor) before the row is marked."""
    rid = row[key]
    upd = lambda **cols: _update_row(pool, table, key, rid, **cols)
    if row["status"] in ("confirmed", "failed"):
        return out
    try:
        just_sent = row["status"] == "signed"
        if just_sent:
            chain.send_raw(bytes(row["raw_tx"]))
            upd(status="broadcast", broadcast_attempts=row["broadcast_attempts"] + 1, last_error=None)
            out["status"] = "broadcast"
        receipt = chain.get_receipt(row["tx_hash"])
        if receipt is None:
            if not just_sent:
                chain.send_raw(bytes(row["raw_tx"]))     # idempotent re-broadcast of identical bytes
            return _no_receipt(row, out, upd=upd, chain=chain, cfg=cfg, now=now, fail=fail)
        if chain.block_number() - receipt["block"] + 1 < cfg.confirmations:
            upd(block_number=receipt["block"])
            return out                                # not final yet, succeeded or reverted: a re-org may flip it
        if receipt["status"] == 0:                   # reverted and deep: no token moved, proven failure
            fail(f"reverted receipt {row['tx_hash']}")
            upd(status="failed", block_number=receipt["block"])
            return {**out, "status": "failed"}
        confirm()
        upd(status="confirmed", block_number=receipt["block"], **done_cols)
        return {**out, "status": "confirmed", "block_number": receipt["block"]}
    except ChainError as e:
        upd(last_error=str(e)[:200])
        return {**out, "error": str(e)[:200]}


def _no_receipt(row, out, *, upd, chain, cfg, now, fail) -> dict:
    """No receipt yet. Fail ONLY on proof: our nonce was consumed by something else,
    seen twice at least `nonce_gone_wait` apart. A timeout alone only marks the transfer 'stuck' (funds stay reserved)."""
    if chain.nonce(row["from_address"], "latest") > row["nonce"]:
        since = row["nonce_gone_since"]
        if since is None:
            upd(nonce_gone_since=now)
        elif now - since >= cfg.nonce_gone_wait:
            fail(f"nonce {row['nonce']} consumed, no receipt for {row['tx_hash']}")
            upd(status="failed")
            out["status"] = "failed"
    else:
        if row["nonce_gone_since"] is not None:
            upd(nonce_gone_since=None)
        if now - row["created_at"] >= cfg.stuck_after and row["status"] != "stuck":
            upd(status="stuck")
            out["status"] = "stuck"
    return out


def reconcile(pool, *, actor, chain, cfg: SettlementConfig, now=None) -> list[dict]:
    """One reconciler pass over every unfinished transfer (also what recovers a crash between commit and broadcast)."""
    with pool.connection() as c:
        ids = [r["transaction_id"] for r in c.execute(
            "SELECT transaction_id FROM chain_settlements WHERE status = ANY(%s) ORDER BY created_at", (list(PENDING),))]
    results = []
    for i in ids:
        try:
            results.append(advance(pool, transaction_id=i, actor=actor, chain=chain, cfg=cfg, now=now))
        except kernel.KernelError as e:              # e.g. NOT_SETTLER for one mandate must not stall the rest
            results.append({"transaction_id": i, "error": e.code})
    return results
