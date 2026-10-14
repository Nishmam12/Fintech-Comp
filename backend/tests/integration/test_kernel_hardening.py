"""Tests added after the independent Opus review: settlement permissions, refused transitions,
human review, proposal expiry, the in-transaction settlement hook, nested reclaim, mandate expiry."""
import time
from datetime import timedelta

import pytest

from budget_kernel import kernel
from budget_kernel.kernel import tx as txmod
from tests.conftest import new_principal, scope


def test_settlement_steps_require_a_settler(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 5_000)["transaction_id"]
    with pytest.raises(kernel.Forbidden):                     # an agent cannot settle its own spend
        kernel.settle_start(world.pool, actor=world.alice, transaction_id=tid)
    kernel.settle_start(world.pool, actor=world.svc, transaction_id=tid)
    with pytest.raises(kernel.Forbidden):                     # the owner can never declare a transfer failed
        kernel.settle_fail(world.pool, actor=world.owner, transaction_id=tid, proof="trust me")
    with pytest.raises(kernel.Forbidden):
        kernel.settle_fail(world.pool, actor=world.alice, transaction_id=tid, proof="trust me")
    assert world.tx(tid)["state"] == "submitted"
    world.check()


def test_refused_transitions_return_conflict_codes(world):
    rej = world.authorize(world.root, world.owner, 1, category="gambling")["transaction_id"]
    prop = world.authorize(world.root, world.owner, 100, needs_review=True)["transaction_id"]
    res = world.authorize(world.root, world.owner, 100)["transaction_id"]
    for tid, code in ((rej, "RELEASE_FROM_REJECTED"), (prop, "RELEASE_FROM_PROPOSED")):
        with pytest.raises(kernel.Conflict) as e:
            kernel.release(world.pool, transaction_id=tid, actor=world.owner)
        assert e.value.code == code
    with pytest.raises(kernel.Conflict) as e:
        kernel.settle_start(world.pool, actor=world.owner, transaction_id=rej)
    assert e.value.code == "SETTLE_FROM_REJECTED"
    with pytest.raises(kernel.Conflict) as e:
        kernel.settle_fail(world.pool, actor=world.svc, transaction_id=res, proof="x")
    assert e.value.code == "FAIL_FROM_RESERVED"
    world.check()


def test_release_by_non_manager_is_forbidden(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 5_000)["transaction_id"]
    with pytest.raises(kernel.Forbidden):
        kernel.release(world.pool, transaction_id=tid, actor=world.bob)
    assert kernel.release(world.pool, transaction_id=tid, actor=world.alice)["state"] == "released"
    world.check()


def test_non_holder_cannot_replay_another_holders_key(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    world.authorize(child, world.alice, 5_000, key="alice-key")
    with pytest.raises(kernel.Forbidden):
        world.authorize(child, world.bob, 5_000, key="alice-key")
    world.check()


def test_idempotency_keys_are_case_sensitive(world):
    a = world.authorize(world.root, world.owner, 1_000, key="AbC")
    b = world.authorize(world.root, world.owner, 1_000, key="abc")
    assert a["transaction_id"] != b["transaction_id"] and not b["replayed"]
    assert world.grant(world.root)["reserved"] == 2_000
    world.check()


def test_delegation_with_past_expiry_is_refused(world):
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(world.root, world.alice, 1_000, expires_at=world.db_now() - timedelta(seconds=5))
    assert e.value.code == "EXPIRY_IN_PAST"


def test_review_approve_reserves_and_deny_rejects(world):
    a = world.authorize(world.root, world.owner, 2_000, needs_review=True)["transaction_id"]
    d = world.authorize(world.root, world.owner, 3_000, needs_review=True)["transaction_id"]
    with pytest.raises(kernel.Forbidden):
        kernel.review(world.pool, transaction_id=a, actor=world.alice, approve=True)
    assert kernel.review(world.pool, transaction_id=a, actor=world.owner, approve=True)["state"] == "reserved"
    out = kernel.review(world.pool, transaction_id=d, actor=world.owner, approve=False)
    assert (out["state"], out["reason"]) == ("rejected", "DENIED_BY_REVIEWER")
    assert kernel.review(world.pool, transaction_id=a, actor=world.owner, approve=False)["replayed"] is True
    assert world.grant(world.root)["reserved"] == 2_000
    world.check()


def test_stale_approval_rechecks_current_state(world):
    """Approving a proposal re-runs every guard: funds spent meanwhile cannot be double-reserved."""
    child = world.delegate(world.root, world.alice, 5_000)["grant_id"]
    prop = world.authorize(child, world.alice, 4_000, needs_review=True)["transaction_id"]
    world.authorize(child, world.alice, 3_000)
    out = kernel.review(world.pool, transaction_id=prop, actor=world.owner, approve=True)
    assert (out["state"], out["reason"]) == ("rejected", "INSUFFICIENT_FUNDS")
    world.check()


def test_unreviewed_proposals_expire(world, monkeypatch):
    monkeypatch.setattr(txmod, "PROPOSAL_TTL_SECONDS", 1)
    prop = world.authorize(world.root, world.owner, 100, needs_review=True)["transaction_id"]
    time.sleep(2)
    world.authorize(world.root, world.owner, 1)              # any op runs the sweep
    t = world.tx(prop)
    assert (t["state"], t["reject_reason"]) == ("rejected", "REVIEW_EXPIRED")
    world.check()


def test_on_submit_hook_runs_in_the_same_transaction(world):
    """ADR-0007 crash window: if persisting the signed transfer fails, the submit rolls back too."""
    tid = world.authorize(world.root, world.owner, 1_000)["transaction_id"]

    def boom(ctx, tx):
        raise RuntimeError("signer crashed")

    with pytest.raises(RuntimeError):
        kernel.settle_start(world.pool, actor=world.svc, transaction_id=tid, on_submit=boom)
    assert world.tx(tid)["state"] == "reserved"
    seen = {}
    kernel.settle_start(world.pool, actor=world.svc, transaction_id=tid,
                        on_submit=lambda ctx, tx: seen.update(state=tx["state"], locked=ctx.mandate_id))
    assert seen == {"state": "submitted", "locked": world.mandate_id}
    world.check()


def test_nested_reclaim_and_late_failure_go_to_nearest_live_ancestor(world):
    mid = world.delegate(world.root, world.alice, 40_000)["grant_id"]
    leaf = world.delegate(mid, world.bob, 10_000, actor=world.alice)["grant_id"]
    tid = world.authorize(leaf, world.bob, 4_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.svc, transaction_id=tid)
    kernel.revoke(world.pool, grant_id=leaf, actor=world.alice)      # leaf revoked; transfer in flight
    assert world.grant(mid)["available"] == 36_000
    kernel.revoke(world.pool, grant_id=mid, actor=world.owner)       # then its parent
    assert world.grant(world.root)["available"] == 86_000
    kernel.settle_fail(world.pool, actor=world.svc, transaction_id=tid, proof="receipt status 0")
    assert world.grant(world.root)["available"] == 90_000            # both revoked: lands on root
    world.check()


def test_mandate_expiry_freezes_and_strands_funds(pool):
    owner = new_principal(pool, "owner", "human")
    with pool.connection() as c:
        soon = c.execute("SELECT now() + interval '6 seconds' AS t").fetchone()["t"]
    m = kernel.create_mandate(pool, owner_principal_id=owner, currency="USD", total=10_000, protected_reserve=0,
                              expires_at=soon, scope=scope())
    time.sleep(7)
    d = kernel.authorize(pool, grant_id=m["root_grant_id"], actor=owner, amount=100, currency="USD",
                         recipient="aws", category="cloud", idempotency_key="late")
    assert (d["state"], d["reason"]) == ("rejected", "MANDATE_FROZEN")
    with pool.connection() as c:
        status = c.execute("SELECT status FROM mandates WHERE id = %s", (m["mandate_id"],)).fetchone()["status"]
    assert status == "frozen"
    assert kernel.check_invariants(pool, m["mandate_id"]) == []
