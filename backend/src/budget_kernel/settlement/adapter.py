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
    explorer: str = "https://sepolia.basescan.org/tx/"

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


def _update(pool, tx_id, **cols) -> None:
    sets = ", ".join(f"{k} = %s" for k in cols)
    with pool.connection() as c:
        c.execute(f"UPDATE chain_settlements SET {sets}, updated_at = now() WHERE transaction_id = %s", (*cols.values(), tx_id))


def advance(pool, *, transaction_id, actor, chain, cfg: SettlementConfig, now=None) -> dict:
    """Move one transfer forward: broadcast the SAME stored bytes, then confirm/fail on proof. Idempotent."""
    now = now or datetime.now(timezone.utc)
    with pool.connection() as c:
        row = c.execute("SELECT * FROM chain_settlements WHERE transaction_id = %s", (transaction_id,)).fetchone()
    if row is None:
        raise SettlementRefused("no signed transfer for this transaction")
    out = {"transaction_id": transaction_id, "tx_hash": row["tx_hash"], "status": row["status"],
           "explorer_url": cfg.explorer_url(row["tx_hash"])}
    if row["status"] in ("confirmed", "failed"):
        return out
    try:
        if row["status"] == "signed":
            chain.send_raw(bytes(row["raw_tx"]))
            _update(pool, transaction_id, status="broadcast", broadcast_attempts=row["broadcast_attempts"] + 1, last_error=None)
            out["status"] = "broadcast"
        receipt = chain.get_receipt(row["tx_hash"])
        if receipt is None:
            chain.send_raw(bytes(row["raw_tx"]))     # idempotent re-broadcast of identical bytes
            return _no_receipt(pool, row, out, actor=actor, chain=chain, cfg=cfg, now=now)
        if receipt["status"] == 0:                   # reverted: no token moved, proven failure
            kernel.settle_fail(pool, transaction_id=transaction_id, actor=actor, proof=f"reverted receipt {row['tx_hash']}")
            _update(pool, transaction_id, status="failed", block_number=receipt["block"])
            return {**out, "status": "failed"}
        if chain.block_number() - receipt["block"] + 1 < cfg.confirmations:
            _update(pool, transaction_id, block_number=receipt["block"])
            return out                                # not deep enough yet; a later call re-checks the receipt (re-org safe)
        kernel.settle_confirm(pool, transaction_id=transaction_id, actor=actor)
        _update(pool, transaction_id, status="confirmed", block_number=receipt["block"], confirmed_at=now)
        return {**out, "status": "confirmed", "block_number": receipt["block"]}
    except ChainError as e:
        _update(pool, transaction_id, last_error=str(e)[:200])
        return {**out, "error": str(e)[:200]}


def _no_receipt(pool, row, out, *, actor, chain, cfg, now) -> dict:
    """No receipt yet. Fail the kernel tx ONLY on proof: our nonce was consumed by something else,
    seen twice at least `nonce_gone_wait` apart. A timeout alone only marks the transfer 'stuck' (funds stay reserved)."""
    tid = row["transaction_id"]
    if chain.nonce(row["from_address"], "latest") > row["nonce"]:
        since = row["nonce_gone_since"]
        if since is None:
            _update(pool, tid, nonce_gone_since=now)
        elif now - since >= cfg.nonce_gone_wait:
            kernel.settle_fail(pool, transaction_id=tid, actor=actor, proof=f"nonce {row['nonce']} consumed, no receipt for {row['tx_hash']}")
            _update(pool, tid, status="failed")
            out["status"] = "failed"
    else:
        if row["nonce_gone_since"] is not None:
            _update(pool, tid, nonce_gone_since=None)
        if now - row["created_at"] >= cfg.stuck_after and row["status"] != "stuck":
            _update(pool, tid, status="stuck")
            out["status"] = "stuck"
    return out


def reconcile(pool, *, actor, chain, cfg: SettlementConfig, now=None) -> list[dict]:
    """One reconciler pass over every unfinished transfer (also what recovers a crash between commit and broadcast)."""
    with pool.connection() as c:
        ids = [r["transaction_id"] for r in c.execute(
            "SELECT transaction_id FROM chain_settlements WHERE status = ANY(%s) ORDER BY created_at", (list(PENDING),))]
    return [advance(pool, transaction_id=i, actor=actor, chain=chain, cfg=cfg, now=now) for i in ids]
