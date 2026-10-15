"""INTENTIONALLY UNSAFE baseline. Do not use for anything but the attack demo.

This is the code most people write first: read the balance, check it in application code, then write.
Each step is a separate round trip with no lock, no conditional UPDATE, no idempotency enforcement
and no ancestor check. It exists so the demo can show -- with measured numbers -- what the
deterministic kernel prevents. Nothing outside budget_kernel.simulation may import this module
(tests/boundary/test_boundaries.py enforces that).
"""
from __future__ import annotations

import uuid


def create_wallet(pool, run_id, available: int, parent_id=None):
    with pool.connection() as c:
        return c.execute("INSERT INTO naive_wallets(run_id, parent_id, available) VALUES (%s,%s,%s) RETURNING id",
                         (run_id, parent_id, available)).fetchone()["id"]


def spend(pool, run_id, wallet_id, amount: int, key: str | None = None) -> bool:
    """UNSAFE read-then-write: two requests can both pass the check, then both debit."""
    with pool.connection() as c:
        w = c.execute("SELECT available, status FROM naive_wallets WHERE id = %s", (wallet_id,)).fetchone()   # read
    if w["status"] != "active" or w["available"] < amount:                                                   # check
        return False
    with pool.connection() as c:                                                                             # write
        c.execute("UPDATE naive_wallets SET available = available - %s WHERE id = %s", (amount, wallet_id))
        c.execute("INSERT INTO naive_spends(run_id, wallet_id, amount, idem_key) VALUES (%s,%s,%s,%s)",
                  (run_id, wallet_id, amount, key))
    return True


def delegate(pool, run_id, parent_id, amount: int):
    """UNSAFE: the parent's balance is checked, then a child is created, then the parent is debited."""
    with pool.connection() as c:
        p = c.execute("SELECT available FROM naive_wallets WHERE id = %s", (parent_id,)).fetchone()
    if p["available"] < amount:
        return None
    with pool.connection() as c:
        child = c.execute("INSERT INTO naive_wallets(run_id, parent_id, available) VALUES (%s,%s,%s) RETURNING id",
                          (run_id, parent_id, amount)).fetchone()["id"]
        c.execute("UPDATE naive_wallets SET available = available - %s WHERE id = %s", (amount, parent_id))
    return child


def revoke(pool, wallet_id) -> None:
    """UNSAFE: marks only this wallet. Descendants stay active and spendable."""
    with pool.connection() as c:
        c.execute("UPDATE naive_wallets SET status = 'revoked' WHERE id = %s", (wallet_id,))


def totals(pool, run_id) -> dict:
    with pool.connection() as c:
        spent = c.execute("SELECT count(*) AS n, coalesce(sum(amount),0)::bigint AS s FROM naive_spends WHERE run_id = %s",
                          (run_id,)).fetchone()
        w = c.execute("SELECT coalesce(sum(available),0)::bigint AS avail, coalesce(min(available),0)::bigint AS lowest"
                      " FROM naive_wallets WHERE run_id = %s", (run_id,)).fetchone()
    return {"spend_count": spent["n"], "spent_total": spent["s"], "balance_total": w["avail"], "lowest_balance": w["lowest"]}


def new_run() -> uuid.UUID:
    return uuid.uuid4()
