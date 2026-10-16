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
        c.execute("TRUNCATE anchors, anchor_heads, chain_settlements, settlement_accounts")
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
    chain.mine(status=0, blocks=2)                      # reverted, 2 confirmations deep
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "failed"
    assert world.tx(tid)["state"] == "released"
    world.check()


def test_shallow_revert_keeps_funds_reserved(env):
    """Review F1: a revert at depth 1 is not final; funds are released only once it is `confirmations` deep."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.mine(status=0, blocks=1)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "broadcast"
    assert world.tx(tid)["state"] == "submitted"
    chain.height += 1
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "failed"
    assert world.tx(tid)["state"] == "released"


def test_revert_reorged_then_success_settles_never_releases(env):
    """Review F1: revert at depth 1, re-org, same bytes mined again and succeed -> settled, never released."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.mine(status=0, blocks=1)
    advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)
    chain.reorg()
    advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)
    chain.mine(status=1, blocks=2)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "confirmed"
    assert world.tx(tid)["state"] == "settled" and len(set(chain.sent)) == 1
    world.check()


def test_reconcile_continues_past_a_refused_transfer(env):
    """Review F2: a transfer the caller may not settle is reported as an error entry; the rest still advance."""
    from tests.conftest import future, new_principal, scope
    from budget_kernel import kernel
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    owner2, svc2 = new_principal(world.pool, "owner2", "human"), new_principal(world.pool, "settler2", "service")
    m2 = kernel.create_mandate(world.pool, owner_principal_id=owner2, currency="USD", total=100_000, protected_reserve=10_000,
                               expires_at=future(30), scope=scope(per_tx_limit=100_000))
    kernel.bind_settler(world.pool, mandate_id=m2["mandate_id"], actor=owner2, principal_id=svc2)
    tid2 = world.authorize(m2["root_grant_id"], owner2, 5_000)["transaction_id"]
    settle(world.pool, transaction_id=tid2, actor=svc2, chain=chain, signer=signer, cfg=cfg)
    chain.mine(blocks=2)
    res = {r["transaction_id"]: r for r in reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)}
    assert res[tid]["status"] == "confirmed" and res[tid2]["error"] == "NOT_SETTLER"
    assert world.tx(tid)["state"] == "settled" and world.tx(tid2)["state"] == "submitted"


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


# ---- review-gate tests (docs/SECURITY_SELF_ASSESSMENT.md section 6) ----

def test_rpc_error_never_releases_funds(env):
    """Gate 1: a dead RPC after broadcast is not proof of failure; the transfer stays submitted and recovers."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.down = True
    assert "error" in advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)
    assert world.tx(tid)["state"] == "submitted"
    chain.down = False
    chain.mine(blocks=2)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "confirmed"


def test_address_in_recipient_field_is_not_an_address(env):
    """Gate 2: only the static registry resolves recipients; a raw 0x address in the request is just an unknown name."""
    world, chain, signer, cfg = env
    from budget_kernel.kernel.errors import Conflict
    tid = world.authorize(world.root, world.owner, 100, recipient="0x" + "ab" * 20)["transaction_id"]
    assert world.tx(tid)["state"] == "rejected"          # the kernel refuses it at authorize; settlement can never see it
    with pytest.raises((SettlementRefused, Conflict)):
        _go(world, chain, signer, cfg, tid)
    assert chain.sent == [] and _row(world.pool, tid) is None


def test_amount_is_integer_base_units_and_usd_only(env):
    """Gate 3: 1 cent = 10_000 base units, exactly; a currency without a registered rate is refused before signing."""
    world, chain, signer, cfg = env
    tid = _reserved(world, amount=1)
    _go(world, chain, signer, cfg, tid)
    amt = _row(world.pool, tid)["token_amount"]
    assert amt == 10_000 and type(int(amt)) is int
    tid2 = _reserved(world, amount=7)
    eur_only = SettlementConfig(recipients={"aws": AWS}, rates={"EUR": 10_000})
    with pytest.raises(SettlementRefused):
        _go(world, chain, signer, eur_only, tid2)
    assert _row(world.pool, tid2) is None and world.tx(tid2)["state"] == "reserved"


def test_on_submit_makes_no_network_call(env, monkeypatch):
    """Gate 5: signing runs under the mandate lock; the chain must not be touched between lock and commit."""
    from budget_kernel import kernel
    world, chain, signer, cfg = env
    calls = {"n": 0, "inside": 0, "in_hook": False}
    for name in ("send_raw", "get_receipt", "nonce", "block_number", "fees"):
        real = getattr(chain, name)
        def wrap(*a, _real=real, **k):
            calls["n"] += 1
            calls["inside"] += calls["in_hook"]
            return _real(*a, **k)
        monkeypatch.setattr(chain, name, wrap)
    real_start = kernel.settle_start
    def spy(pool, *, transaction_id, actor, on_submit=None):
        def hook(ctx, tx):
            calls["in_hook"] = True
            try:
                on_submit(ctx, tx)
            finally:
                calls["in_hook"] = False
        return real_start(pool, transaction_id=transaction_id, actor=actor, on_submit=hook)
    monkeypatch.setattr(kernel, "settle_start", spy)
    _go(world, chain, signer, cfg, _reserved(world))
    assert calls["n"] > 0 and calls["inside"] == 0


def test_private_key_never_appears_in_errors_db_or_audit(env):
    """Gate 6: trigger refusals and outages, then search every surface for the key."""
    import json
    world, chain, signer, cfg = env
    key = "22" * 32
    texts = [repr(signer), str(signer)]
    tid = world.authorize(world.root, world.owner, 100, recipient="google")["transaction_id"]
    with pytest.raises(SettlementRefused) as e1:
        _go(world, chain, signer, cfg, tid)
    texts.append(repr(e1.value))
    tid2 = _reserved(world)
    chain.down = True
    texts.append(json.dumps(_go(world, chain, signer, cfg, tid2), default=str))   # outage text returned to the caller
    chain.down = False
    chain.mine(status=0)
    reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)                   # also writes a settle_failed audit row
    with world.pool.connection() as c:
        for table in ("chain_settlements", "audit_events", "transactions", "settlement_accounts"):
            texts += [json.dumps(r, default=str) for r in c.execute(f"SELECT * FROM {table}").fetchall()]
    blob = "\n".join(texts).lower()
    assert key not in blob


def test_crash_after_broadcast_before_status_write_resends_same_bytes(env):
    """Gate 8b: node got the tx but we died before recording 'broadcast': the stored row is still 'signed';
    recovery re-sends the identical bytes (never re-signs) and the transfer settles exactly once."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    row = _row(world.pool, tid)
    with world.pool.connection() as c:
        c.execute("UPDATE chain_settlements SET status='signed' WHERE transaction_id=%s", (tid,))   # simulate the lost write
    chain.mine(blocks=2)                                                                            # tx is already in a block
    reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)
    assert world.tx(tid)["state"] == "settled" and _row(world.pool, tid)["raw_tx"] == row["raw_tx"]
    with world.pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM chain_settlements").fetchone()["n"] == 1


def test_crash_after_broadcast_before_confirm_is_recovered_by_reconcile(env):
    """Gate 8c: process dies after broadcast, before settle_confirm; a fresh reconcile pass confirms it."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.mine(blocks=2)
    assert world.tx(tid)["state"] == "submitted"           # nobody called confirm: this is the crash window
    reconcile(world.pool, actor=world.svc, chain=chain, cfg=cfg)
    assert world.tx(tid)["state"] == "settled"
    world.check()


def test_reorg_before_depth_does_not_confirm_or_fail(env):
    """BK-311: a receipt that vanishes (re-org) before it is `confirmations` deep never settles or releases;
    the same bytes are re-sent and the transfer confirms when it is deep enough again."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    _go(world, chain, signer, cfg, tid)
    chain.mine(blocks=0)                                   # included, 1 confirmation
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "broadcast"
    chain.reorg()
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "broadcast"
    assert world.tx(tid)["state"] == "submitted" and len(set(chain.sent)) == 1     # same hash, never re-signed
    chain.mine(blocks=2)
    assert advance(world.pool, transaction_id=tid, actor=world.svc, chain=chain, cfg=cfg)["status"] == "confirmed"


def test_gas_ceiling_waits_without_consuming_a_nonce(env):
    """BK-312: above the ceiling nothing is signed and no nonce is used; when gas drops, the first transfer gets nonce 0."""
    world, chain, signer, cfg = env
    tid = _reserved(world)
    chain.base_fee = 10**12
    with pytest.raises(SettlementRefused):
        _go(world, chain, signer, cfg, tid)
    with world.pool.connection() as c:
        assert c.execute("SELECT next_nonce FROM settlement_accounts").fetchone()["next_nonce"] == 0
    chain.base_fee = 10**9
    _go(world, chain, signer, cfg, tid)
    assert _row(world.pool, tid)["nonce"] == 0 and world.tx(tid)["state"] == "submitted"
