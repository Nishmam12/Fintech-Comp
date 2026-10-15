"""Settlement adapter vs the real DB and a FakeChain (ADR-0007 crash windows). No network, no real key."""
from __future__ import annotations

from datetime import timedelta

import pytest

from budget_kernel.settlement.adapter import SettlementConfig, SettlementRefused, advance, reconcile, settle
from budget_kernel.settlement.chain import ChainError
from budget_kernel.settlement.fake import FakeChain
from budget_kernel.settlement.signer import Signer

AWS = "0x00000000000000000000000000000000000A5300"


@pytest.fixture()
def env(world, pool):
    pool_ = pool
    with pool_.connection() as c:
        c.execute("TRUNCATE chain_settlements, settlement_accounts")
    cfg = SettlementConfig(recipients={"aws": AWS})
    return world, FakeChain(), Signer("0x" + "22" * 32), cfg


def _reserved(world, amount=5_000):
    return world.authorize(world.root, world.owner, amount)["transaction_id"]


def _row(pool, tid):
    with pool.connection() as c:
        return c.execute("SELECT * FROM chain_settlements WHERE transaction_id=%s", (tid,)).fetchone()


def _go(world, chain, signer, cfg, tid, **kw):
    return settle(world.pool, transaction_id=tid, actor=world.svc, chain=chain, signer=signer, cfg=cfg, **kw)


def test_happy_path_settles_after_confirmations(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    out = _go(world, chain, signer, cfg, tid)
    assert out["status"] == "broadcast" and len(chain.sent) == 1
    chain.mine(blocks=1)                               # receipt at height+1, 1 confirmation: not enough
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "broadcast"
    assert world.tx(tid)["state"] == "submitted"
    chain.height += 1                                  # 2 confirmations
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "confirmed"
    assert world.tx(tid)["state"] == "settled" and _row(world.pool, tid)["token_amount"] == 5_000 * 10_000
    world.check()


def test_crash_after_commit_before_broadcast_resends_same_bytes_once(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    chain.down = True
    assert "error" in _go(world, chain, signer, cfg, tid)       # signed + committed, broadcast failed
    row = _row(world.pool, tid)
    assert row["status"] == "signed" and world.tx(tid)["state"] == "submitted" and chain.sent == []
    chain.down = False
    reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)
    assert chain.sent == [row["tx_hash"]] and _row(world.pool, tid)["raw_tx"] == row["raw_tx"]
    chain.mine(blocks=2)
    reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)
    assert world.tx(tid)["state"] == "settled"


def test_repeated_settle_signs_once(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    for _ in range(3):
        _go(world, chain, signer, cfg, tid)
    with world.pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM chain_settlements").fetchone()["n"] == 1
        assert c.execute("SELECT next_nonce FROM settlement_accounts").fetchone()["next_nonce"] == 1
    assert set(chain.sent) == {_row(world.pool, tid)["tx_hash"]}


def test_revert_releases_funds(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.mine(status=0)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "failed"
    assert world.tx(tid)["state"] == "released"
    world.check()


def test_unregistered_recipient_and_gas_ceiling_leave_tx_reserved(env):
    world, chain, signer, cfg = env
    tid = world.authorize(world.root, world.owner, 100, recipient="google")["transaction_id"]
    with pytest.raises(SettlementRefused):
        _go(world, chain, signer, cfg, tid)
    tid2 = _reserved(world)
    chain.base_fee = 10**12                              # above ceiling
    with pytest.raises(SettlementRefused):
        _go(world, chain, signer, cfg, tid2)
    assert world.tx(tid)["state"] == world.tx(tid2)["state"] == "reserved" and chain.sent == []


def test_timeout_alone_never_releases(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    later = world.db_now() + timedelta(hours=2)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg, now=later)["status"] == "stuck"
    assert world.tx(tid)["state"] == "submitted"         # still reserved


def test_nonce_consumed_releases_only_after_two_checks(env):
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.nonce_override = 5                              # someone else used our nonce; no receipt for our hash
    t0 = world.db_now()
    advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg, now=t0)
    assert world.tx(tid)["state"] == "submitted"
    advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg, now=t0 + timedelta(seconds=61))
    assert world.tx(tid)["state"] == "released"


def test_owner_cannot_fail_a_transfer(env):
    from budget_kernel.kernel.errors import Forbidden
    from budget_kernel import kernel
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    with pytest.raises(Forbidden):
        kernel.settle_fail(world.pool, transaction_id=tid, actor=world.owner, proof="x")
