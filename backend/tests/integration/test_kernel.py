"""Kernel behaviour against real Postgres. I1-I3 are asserted after every step (ADR-0004)."""
import time
import uuid

import pytest

from budget_kernel import kernel
from budget_kernel.kernel import ops
from tests.conftest import future, scope


# ------------------------------------------------------------------ mandate / authorize

def test_mandate_root_excludes_protected_reserve(world):
    g = world.grant(world.root)
    assert (g["available"], g["reserved"], g["settled"]) == (90_000, 0, 0)


def test_protected_reserve_is_not_spendable(world):
    d = world.authorize(world.root, world.owner, 90_001)
    assert (d["state"], d["reason"]) == ("rejected", "INSUFFICIENT_FUNDS")
    ok = world.authorize(world.root, world.owner, 90_000)
    assert ok["state"] == "reserved"
    world.check()


def test_authorize_moves_available_to_reserved(world):
    d = world.authorize(world.root, world.owner, 25_000)
    assert d["state"] == "reserved"
    g = world.grant(world.root)
    assert (g["available"], g["reserved"]) == (65_000, 25_000)
    world.check()


@pytest.mark.parametrize("kw,reason", [
    ({"category": "gambling"}, "CATEGORY_NOT_ALLOWED"),
    ({"recipient": "evil-corp"}, "RECIPIENT_NOT_ALLOWED"),
    ({"currency": "EUR"}, "CURRENCY_MISMATCH"),
])
def test_rejections_change_no_balances(world, kw, reason):
    before = world.grant(world.root)
    d = world.authorize(world.root, world.owner, 1_000, **kw)
    assert (d["state"], d["reason"]) == ("rejected", reason)
    after = world.grant(world.root)
    assert (before["available"], before["reserved"]) == (after["available"], after["reserved"])
    world.check()


def test_per_tx_limit_enforced_on_child(world):
    child = world.delegate(world.root, world.alice, 40_000, scope=scope(per_tx_limit=5_000))["grant_id"]
    assert world.authorize(child, world.alice, 5_001)["reason"] == "PER_TX_LIMIT_EXCEEDED"
    assert world.authorize(child, world.alice, 5_000)["state"] == "reserved"
    world.check()


@pytest.mark.parametrize("bad", [0, -5, 1.5, "100", True, None])
def test_bad_amounts_are_rejected_before_any_state_change(world, bad):
    with pytest.raises(kernel.ValidationFailed):
        world.authorize(world.root, world.owner, bad)
    world.check()


def test_model_claimed_authorization_is_just_stored_text(world):
    """ADR-0001: a proposal saying authorized=true grants nothing; review-needed holds no funds."""
    d = world.authorize(world.root, world.owner, 5_000, needs_review=True,
                        proposal={"authorized": True, "approved_by": "model"})
    assert d["state"] == "proposed"
    g = world.grant(world.root)
    assert (g["available"], g["reserved"]) == (90_000, 0)
    world.check()


# ------------------------------------------------------------------ delegation / attenuation

def test_delegation_moves_funds_not_creates_them(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    assert world.grant(world.root)["available"] == 60_000
    assert world.grant(child)["available"] == 30_000
    world.check()


def test_child_cannot_exceed_parent_available(world):
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(world.root, world.alice, 90_001)
    assert e.value.code == "INSUFFICIENT_FUNDS"
    world.check()


def test_children_cannot_sum_past_parent(world):
    world.delegate(world.root, world.alice, 60_000)
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(world.root, world.bob, 30_001)
    assert e.value.code == "INSUFFICIENT_FUNDS"
    world.delegate(world.root, world.bob, 30_000)
    world.check()


@pytest.mark.parametrize("wide", [
    {"categories": ["cloud", "ads", "travel"]},
    {"recipients": ["aws", "google", "meta"]},
    {"per_tx_limit": 100_001},
])
def test_scope_cannot_widen_through_delegation(world, wide):
    mid = world.delegate(world.root, world.alice, 40_000, scope=scope(per_tx_limit=50_000))["grant_id"]
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(mid, world.bob, 1_000, actor=world.alice, scope=scope(**wide))
    assert e.value.code == "SCOPE_WIDER_THAN_PARENT"
    world.check()


def test_child_expiry_cannot_exceed_parent(world):
    mid = world.delegate(world.root, world.alice, 40_000, expires_at=future(5))["grant_id"]
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(mid, world.bob, 1_000, actor=world.alice, expires_at=future(6))
    assert e.value.code == "EXPIRY_EXCEEDS_PARENT"


def test_non_delegating_grant_cannot_delegate(world):
    leaf = world.delegate(world.root, world.alice, 40_000, scope=scope(can_delegate=False))["grant_id"]
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(leaf, world.bob, 1_000, actor=world.alice, scope=scope(can_delegate=False))
    assert e.value.code == "PARENT_CANNOT_DELEGATE"


def test_depth_cap(world):
    parent, actor, holders = world.root, world.owner, [world.alice, world.bob, world.alice, world.bob]
    for h in holders:
        parent_next = world.delegate(parent, h, 10_000, actor=actor)["grant_id"]
        parent, actor = parent_next, h
    with pytest.raises(kernel.DelegationRejected) as e:
        world.delegate(parent, world.alice, 100, actor=actor)
    assert e.value.code == "MAX_DEPTH_EXCEEDED"
    world.check()


def test_only_holder_can_delegate_or_authorize(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    with pytest.raises(kernel.Forbidden):
        world.authorize(child, world.bob, 100)
    with pytest.raises(kernel.Forbidden):
        world.delegate(child, world.bob, 100, actor=world.bob)
    assert "NOT_GRANT_HOLDER" in world.audit_kinds()  # refusals are audited
    world.check()


def test_scope_is_immutable_in_the_database(world):
    with pytest.raises(Exception, match="immutable"):
        with world.pool.connection() as c:
            c.execute("UPDATE grants SET scope = '{}'::jsonb WHERE id = %s", (world.root,))


# ------------------------------------------------------------------ idempotency

def test_same_key_same_payload_replays_the_stored_decision(world):
    a = world.authorize(world.root, world.owner, 1_000, key="k1")
    b = world.authorize(world.root, world.owner, 1_000, key="k1")
    assert (a["transaction_id"], b["replayed"]) == (b["transaction_id"], True)
    assert world.grant(world.root)["reserved"] == 1_000  # reserved once
    world.check()


def test_same_key_different_payload_is_a_conflict_and_audited(world):
    world.authorize(world.root, world.owner, 1_000, key="k2")
    with pytest.raises(kernel.IdempotencyConflict):
        world.authorize(world.root, world.owner, 2_000, key="k2")
    assert "IDEMPOTENCY_CONFLICT" in world.audit_kinds()
    assert world.grant(world.root)["reserved"] == 1_000
    world.check()


def test_rejection_is_replayed_not_reevaluated(world):
    """A retry must never flip a rejection into an approval after funds are freed."""
    child = world.delegate(world.root, world.alice, 1_000)["grant_id"]
    big = world.authorize(child, world.alice, 900, key="hold")
    rej = world.authorize(child, world.alice, 500, key="retry-me")
    assert rej["state"] == "rejected"
    kernel.release(world.pool, transaction_id=big["transaction_id"], actor=world.alice)
    again = world.authorize(child, world.alice, 500, key="retry-me")
    assert (again["state"], again["replayed"]) == ("rejected", True)
    assert world.authorize(child, world.alice, 500, key="fresh-key")["state"] == "reserved"
    world.check()


def test_delegation_idempotency(world):
    a = world.delegate(world.root, world.alice, 5_000, key="d1")
    b = world.delegate(world.root, world.alice, 5_000, key="d1")
    assert (a["grant_id"], b["replayed"]) == (b["grant_id"], True)
    assert world.grant(world.root)["available"] == 85_000
    with pytest.raises(kernel.IdempotencyConflict):
        world.delegate(world.root, world.alice, 6_000, key="d1")
    world.check()


# ------------------------------------------------------------------ lifecycle

def test_full_lifecycle_reserve_submit_settle(world):
    tid = world.authorize(world.root, world.owner, 10_000)["transaction_id"]
    assert kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)["state"] == "submitted"
    world.check()
    assert kernel.settle_confirm(world.pool, actor=world.owner, transaction_id=tid)["state"] == "settled"
    g = world.grant(world.root)
    assert (g["available"], g["reserved"], g["settled"]) == (80_000, 0, 10_000)
    world.check()


def test_repeated_transitions_are_idempotent_or_conflict(world):
    tid = world.authorize(world.root, world.owner, 10_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    assert kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)["replayed"] is True       # no second submit
    with pytest.raises(kernel.Conflict) as e:                                              # in flight cannot be released
        kernel.release(world.pool, transaction_id=tid, actor=world.owner)
    assert e.value.code == "RELEASE_FROM_SUBMITTED"
    kernel.settle_confirm(world.pool, actor=world.owner, transaction_id=tid)
    assert kernel.settle_confirm(world.pool, actor=world.owner, transaction_id=tid)["replayed"] is True
    with pytest.raises(kernel.Conflict):
        kernel.release(world.pool, transaction_id=tid, actor=world.owner)                 # settled funds are not restored
    world.check()


def test_release_returns_funds_and_is_idempotent(world):
    tid = world.authorize(world.root, world.owner, 7_000)["transaction_id"]
    assert kernel.release(world.pool, transaction_id=tid, actor=world.owner)["replayed"] is False
    assert kernel.release(world.pool, transaction_id=tid, actor=world.owner)["replayed"] is True
    assert world.grant(world.root)["available"] == 90_000
    with pytest.raises(kernel.Conflict):
        kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    world.check()


def test_failed_transfer_releases_only_with_proof(world):
    tid = world.authorize(world.root, world.owner, 4_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    with pytest.raises(kernel.ValidationFailed):
        kernel.settle_fail(world.pool, actor=world.svc, transaction_id=tid, proof="")
    assert kernel.settle_fail(world.pool, actor=world.svc, transaction_id=tid, proof="receipt status 0")["state"] == "released"
    assert world.grant(world.root)["available"] == 90_000
    world.check()


# ------------------------------------------------------------------ revocation

def test_revoke_releases_reservations_and_returns_funds_up(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    out = kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    assert (out["reclaimed"], out["released_reservations"], out["in_flight_count"]) == (30_000, 1, 0)
    assert world.tx(tid)["state"] == "released"
    assert world.grant(world.root)["available"] == 90_000
    d = world.authorize(child, world.alice, 100)
    assert (d["state"], d["reason"]) == ("rejected", "GRANT_REVOKED")
    world.check()


def test_revoked_ancestor_blocks_active_descendants(world):
    mid = world.delegate(world.root, world.alice, 40_000)["grant_id"]
    leaf = world.delegate(mid, world.bob, 10_000, actor=world.alice)["grant_id"]
    kernel.revoke(world.pool, grant_id=mid, actor=world.owner)
    assert world.grant(leaf)["status"] == "revoked"
    assert world.authorize(leaf, world.bob, 100)["reason"] == "GRANT_REVOKED"
    world.check()


def test_revoke_does_not_undo_settled_spend(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    kernel.settle_confirm(world.pool, actor=world.owner, transaction_id=tid)
    kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    assert world.grant(child)["settled"] == 10_000
    assert world.grant(world.root)["available"] == 80_000   # 60_000 untouched + 20_000 reclaimed
    world.check()


def test_in_flight_transfer_survives_revocation_and_is_reported(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    out = kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    assert (out["in_flight_count"], out["in_flight_amount"]) == (1, 10_000)
    assert world.tx(tid)["state"] == "submitted"
    assert kernel.settle_confirm(world.pool, actor=world.owner, transaction_id=tid)["state"] == "settled"
    world.check()


def test_failed_in_flight_transfer_after_revocation_goes_to_live_ancestor(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    kernel.settle_fail(world.pool, actor=world.svc, transaction_id=tid, proof="receipt status 0")
    assert world.grant(child)["available"] == 0 and world.grant(child)["reserved"] == 0
    assert world.grant(world.root)["available"] == 90_000
    world.check()


def test_settle_start_after_revoke_is_refused(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    tid = world.authorize(child, world.alice, 10_000)["transaction_id"]
    kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    with pytest.raises(kernel.Conflict):
        kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    world.check()


def test_revoke_root_freezes_mandate_and_strands_funds(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    out = kernel.revoke(world.pool, grant_id=world.root, actor=world.owner)
    assert out["stranded_on_root"] is True
    assert world.grant(world.root)["available"] == 90_000
    assert world.authorize(child, world.alice, 100)["state"] == "rejected"
    with pytest.raises(kernel.DelegationRejected):
        world.delegate(world.root, world.bob, 1)
    world.check()


def test_revoke_is_idempotent_and_permissioned(world):
    child = world.delegate(world.root, world.alice, 30_000)["grant_id"]
    with pytest.raises(kernel.Forbidden):
        kernel.revoke(world.pool, grant_id=child, actor=world.bob)
    with pytest.raises(kernel.Forbidden):
        kernel.revoke(world.pool, grant_id=child, actor=world.alice)   # a holder cannot revoke their own grant
    kernel.revoke(world.pool, grant_id=child, actor=world.owner)
    assert kernel.revoke(world.pool, grant_id=child, actor=world.owner)["already"] is True
    world.check()


def test_ancestor_holder_can_revoke_descendant(world):
    mid = world.delegate(world.root, world.alice, 40_000)["grant_id"]
    leaf = world.delegate(mid, world.bob, 10_000, actor=world.alice)["grant_id"]
    assert kernel.revoke(world.pool, grant_id=leaf, actor=world.alice)["reclaimed"] == 10_000
    assert world.grant(mid)["available"] == 40_000
    world.check()


# ------------------------------------------------------------------ expiry

def test_expired_grant_blocks_authorization_and_is_reclaimed(world):
    from datetime import timedelta
    soon = world.db_now() + timedelta(seconds=6)
    child = world.delegate(world.root, world.alice, 30_000, expires_at=soon)["grant_id"]
    time.sleep(7)
    d = world.authorize(child, world.alice, 100)
    assert (d["state"], d["reason"]) == ("rejected", "GRANT_EXPIRED")
    assert world.grant(child)["status"] == "expired"
    assert world.grant(world.root)["available"] == 90_000
    world.check()


def test_stale_reservation_is_released_by_ttl(world, monkeypatch):
    monkeypatch.setattr(ops, "RESERVE_TTL_SECONDS", 1)
    tid = world.authorize(world.root, world.owner, 5_000)["transaction_id"]
    time.sleep(2)
    world.authorize(world.root, world.owner, 100)      # any op triggers the lazy sweep
    assert world.tx(tid)["state"] == "released"
    assert world.grant(world.root)["available"] == 89_900
    world.check()


def test_expired_reservation_cannot_be_submitted(world, monkeypatch):
    monkeypatch.setattr(ops, "RESERVE_TTL_SECONDS", 1)
    tid = world.authorize(world.root, world.owner, 5_000)["transaction_id"]
    time.sleep(2)
    with pytest.raises(kernel.Conflict) as e:
        kernel.settle_start(world.pool, actor=world.owner, transaction_id=tid)
    # The lock-scoped sweep releases the stale reservation before settle-start looks at it.
    assert e.value.code == "SETTLE_FROM_RELEASED"
    assert world.tx(tid)["state"] == "released"
    world.check()


# ------------------------------------------------------------------ audit / ledger are append-only

def test_audit_and_movements_are_append_only(world):
    world.authorize(world.root, world.owner, 100)
    for table in ("audit_events", "ledger_movements"):
        with pytest.raises(Exception, match="append-only"):
            with world.pool.connection() as c:
                c.execute(f"DELETE FROM {table} WHERE mandate_id = %s", (world.mandate_id,))
