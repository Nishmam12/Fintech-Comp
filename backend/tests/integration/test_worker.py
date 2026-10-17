"""BK-403: one worker pass advances a mined transfer and releases an expired reservation; failures never kill the loop."""
from __future__ import annotations

import time

from budget_kernel import worker
from budget_kernel.settlement.adapter import SettlementConfig, settle
from budget_kernel.settlement.fake import FakeChain
from budget_kernel.settlement.signer import Signer


def test_one_pass_settles_mined_transfer_and_releases_expired_reservation(world, pool):
    with pool.connection() as c:
        c.execute("TRUNCATE anchors, anchor_heads, chain_settlements, settlement_accounts")
    chain, signer = FakeChain(), Signer("0x" + "22" * 32)
    cfg = SettlementConfig(recipients={"aws": "0x00000000000000000000000000000000000A5300"})
    paid = world.authorize(world.root, world.owner, 5_000)["transaction_id"]
    settle(pool, transaction_id=paid, actor=world.svc, chain=chain, signer=signer, cfg=cfg)
    chain.mine(blocks=2)
    stale = world.authorize(world.root, world.owner, 1_000)["transaction_id"]
    with pool.connection() as c:       # age the reservation past its TTL (the sweep reads the DB clock)
        c.execute("ALTER TABLE transactions DISABLE TRIGGER USER")
        c.execute("UPDATE transactions SET reserve_expires_at = now() - interval '1 minute' WHERE id = %s", (stale,))
        c.execute("ALTER TABLE transactions ENABLE TRIGGER USER")
    out = worker.run_once(pool, settlement=(chain, signer, cfg), actor=world.svc)
    assert world.tx(paid)["state"] == "settled" and world.tx(stale)["state"] == "released", out
    assert not any(str(v).startswith("error") for v in out.values()), out
    world.check()


def test_failing_step_is_isolated_and_loop_survives(pool, monkeypatch):
    def boom(_pool):
        raise RuntimeError("0xdeadbeef raw tx")
    monkeypatch.setattr(worker.cost_ledger, "sweep_stale", boom)
    out = worker.run_once(pool)
    assert out["cost_sweep"] == "error:RuntimeError" and isinstance(out["ticks"], int)   # message never kept
    w = worker.Worker(pool, interval=0.05).start()
    time.sleep(0.3)
    assert w._thread.is_alive()
    w.stop()
    assert not w._thread.is_alive()
