"""Races against the real database (ADR-0005 'Evidence and validation').

Threads are released together by a barrier so their kernel calls genuinely contend for the
mandate lock. Whatever the interleaving, I1-I3 must hold and no money may be created or lost.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from budget_kernel import kernel
from budget_kernel.kernel import tx as kernel_tx_module

pytestmark = pytest.mark.concurrency


@pytest.fixture(autouse=True)
def patient_locks(monkeypatch):
    # ~60 ms per round trip means each op holds the lock ~0.6 s; let waiters queue instead of timing out.
    monkeypatch.setattr(kernel_tx_module, "LOCK_TIMEOUT_MS", 120_000)
    # statement_timeout also counts time spent waiting for the row lock, so at ~100 ms per round trip the last of eight
    # queued racers would hit the 5 s production limit and get KernelBusy (a designed, retryable refusal, not an
    # overspend). These tests assert I1-I3 under contention, so let them queue; KernelBusy has its own tests.
    monkeypatch.setattr(kernel_tx_module, "STATEMENT_TIMEOUT_MS", 120_000)


def race(fns):
    """Run callables simultaneously; return [(ok, value_or_exception), ...] in the same order."""
    barrier = threading.Barrier(len(fns))

    def run(fn):
        barrier.wait()
        try:
            return True, fn()
        except Exception as exc:  # noqa: BLE001 - outcomes are asserted by the caller
            return False, exc

    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        return [f.result() for f in [ex.submit(run, fn) for fn in fns]]


def test_overspend_race_exactly_k_of_n_succeed(world):
    """8 racers each ask for 30_000 against a grant holding 90_000: exactly 3 may be approved."""
    results = race([lambda: world.authorize(world.root, world.owner, 30_000) for _ in range(8)])
    assert all(ok for ok, _ in results)
    states = sorted(v["state"] for _, v in results)
    assert states.count("reserved") == 3 and states.count("rejected") == 5
    g = world.grant(world.root)
    assert (g["available"], g["reserved"]) == (0, 90_000)
    world.check()


def test_sibling_delegations_cannot_exceed_parent(world):
    """6 racers each delegate 20_000 from a parent holding 90_000: exactly 4 succeed."""
    results = race([lambda: world.delegate(world.root, world.alice, 20_000) for _ in range(6)])
    ok = [r for r, _ in results if r]
    assert len(ok) == 4
    assert all(isinstance(v, kernel.DelegationRejected) and v.code == "INSUFFICIENT_FUNDS" for r, v in results if not r)
    assert world.grant(world.root)["available"] == 10_000
    world.check()


def test_delegate_vs_authorize_on_same_parent_never_overspends(world):
    results = race(
        [lambda: world.delegate(world.root, world.alice, 60_000) for _ in range(2)]
        + [lambda: world.authorize(world.root, world.owner, 50_000) for _ in range(2)]
    )
    g = world.grant(world.root)
    assert g["available"] >= 0 and g["reserved"] in (0, 50_000, 100_000)
    world.check()
    assert not [v for ok, v in results if not ok and not isinstance(v, kernel.DelegationRejected)]


def test_same_idempotency_key_ten_ways_creates_one_transaction(world):
    key = uuid.uuid4().hex
    results = race([lambda: world.authorize(world.root, world.owner, 4_000, key=key) for _ in range(6)])
    assert all(ok for ok, _ in results)
    assert len({v["transaction_id"] for _, v in results}) == 1
    assert world.grant(world.root)["reserved"] == 4_000
    world.check()


@pytest.mark.parametrize("round_", range(3))
def test_revoke_vs_authorize_both_orderings_stay_consistent(world, round_):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    results = race([
        lambda: kernel.revoke(world.pool, grant_id=child, actor=world.owner),
        lambda: world.authorize(child, world.alice, 10_000),
    ])
    assert all(ok for ok, _ in results), results
    decision = results[1][1]
    if decision["state"] == "reserved":      # authorize won: revoke must have released it
        assert world.tx(decision["transaction_id"])["state"] == "released"
    else:                                    # revoke won: authorize must be refused
        assert decision["reason"] == "GRANT_REVOKED"
    g = world.grant(child)
    assert (g["status"], g["available"], g["reserved"]) == ("revoked", 0, 0)
    assert world.grant(world.root)["available"] == 90_000
    world.check()


@pytest.mark.parametrize("round_", range(3))
def test_revoke_vs_settle_start_never_leaves_funds_unaccounted(world, round_):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    results = race([
        lambda: kernel.revoke(world.pool, grant_id=child, actor=world.owner),
        lambda: kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid),
    ])
    revoke_res = results[0][1]
    assert results[0][0]
    ok_settle, settle_res = results[1]
    if ok_settle:                            # settle-start won: in flight, reported as exposure
        assert revoke_res["in_flight_amount"] == 10_000
        assert world.tx(tid)["state"] == "submitted"
    else:                                    # revoke won: reservation released, settle refused
        assert isinstance(settle_res, kernel.Conflict)
        assert world.tx(tid)["state"] == "released"
    world.check()


def test_duplicate_settle_start_never_submits_twice(world):
    tid = world.authorize(world.root, world.owner, 5_000)["transaction_id"]
    results = race([lambda: kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid) for _ in range(5)])
    assert all(ok for ok, _ in results)
    assert sum(1 for _, v in results if not v["replayed"]) == 1
    with world.pool.connection() as c:
        n = c.execute("SELECT count(*) AS n FROM audit_events WHERE subject_id = %s AND kind = 'TX_SUBMITTED'",
                      (tid,)).fetchone()["n"]
    assert n == 1
    world.check()


def test_lock_timeout_fails_closed_not_open(world, monkeypatch):
    """A caller that cannot get the lock in time gets a retryable error and no approval."""
    monkeypatch.setattr(kernel_tx_module, "LOCK_TIMEOUT_MS", 300)
    hold, release_hold = threading.Event(), threading.Event()

    def holder():
        with world.pool.connection() as c:
            with c.transaction():
                c.execute("SELECT 1 FROM mandates WHERE id = %s FOR UPDATE", (world.mandate_id,))
                hold.set()
                release_hold.wait(20)

    t = threading.Thread(target=holder)
    t.start()
    hold.wait(10)
    try:
        with pytest.raises(kernel.KernelBusy):
            world.authorize(world.root, world.owner, 1_000)
    finally:
        release_hold.set()
        t.join()
    assert world.grant(world.root)["reserved"] == 0
    world.check()
