"""ADR-0008: rolling velocity windows over the grant subtree, and the owner-approval threshold."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from budget_kernel import kernel
from budget_kernel.api.app import create_app
from tests.conftest import scope

WINDOW = {"window_limit": 30_000, "window_seconds": 3600}


def grant_for(w, holder, amount=60_000, **scope_over):
    return w.delegate(w.root, holder, amount, scope=scope(**scope_over))["grant_id"]


def states(results):
    return [r["state"] for r in results]


# ------------------------------------------------------------------ velocity

def test_window_limit_refuses_the_spend_that_would_exceed_it(world):
    g = grant_for(world, world.alice, **WINDOW)
    res = [world.authorize(g, world.alice, 10_000) for _ in range(4)]
    assert states(res) == ["reserved", "reserved", "reserved", "rejected"]
    assert res[3]["reason"] == "VELOCITY_LIMIT_EXCEEDED"
    world.check()


def test_a_parent_window_binds_every_descendant(world):
    parent = grant_for(world, world.alice, 60_000, window_limit=20_000, window_seconds=3600)
    child = world.delegate(parent, world.bob, 30_000, actor=world.alice, scope=scope())["grant_id"]  # omits the window
    assert world.authorize(parent, world.alice, 10_000)["state"] == "reserved"      # parent's own spend counts
    assert world.authorize(child, world.bob, 10_000)["state"] == "reserved"
    refused = world.authorize(child, world.bob, 10_000)
    assert refused["reason"] == "VELOCITY_LIMIT_EXCEEDED"                            # subtree total hit 20,000
    world.check()


def test_spend_outside_the_window_stops_counting(world):
    g = grant_for(world, world.alice, window_limit=20_000, window_seconds=60)
    first = [world.authorize(g, world.alice, 10_000) for _ in range(2)]
    assert world.authorize(g, world.alice, 10_000)["reason"] == "VELOCITY_LIMIT_EXCEEDED"
    with world.pool.connection() as c:                                               # age the reservations past the window
        c.execute("UPDATE transactions SET reserved_at = reserved_at - interval '2 minutes' WHERE id = ANY(%s)",
                  ([r["transaction_id"] for r in first],))
    assert world.authorize(g, world.alice, 10_000)["state"] == "reserved"
    world.check()


def test_released_spend_frees_capacity_but_settled_spend_keeps_counting(world):
    g = grant_for(world, world.alice, window_limit=20_000, window_seconds=3600)
    a = world.authorize(g, world.alice, 10_000)
    b = world.authorize(g, world.alice, 10_000)
    assert world.authorize(g, world.alice, 10_000)["reason"] == "VELOCITY_LIMIT_EXCEEDED"
    kernel.release(world.pool, transaction_id=a["transaction_id"], actor=world.alice)
    c3 = world.authorize(g, world.alice, 10_000)
    assert c3["state"] == "reserved"                                                 # released money was not spent
    kernel.settle_start(world.pool, transaction_id=b["transaction_id"], actor=world.owner)
    kernel.settle_confirm(world.pool, transaction_id=b["transaction_id"], actor=world.owner)
    kernel.release(world.pool, transaction_id=c3["transaction_id"], actor=world.alice)
    assert world.authorize(g, world.alice, 20_000)["reason"] == "VELOCITY_LIMIT_EXCEEDED"   # 10,000 settled still counts
    assert world.authorize(g, world.alice, 10_000)["state"] == "reserved"
    world.check()


def test_concurrent_spends_cannot_overshoot_the_window(world):
    g = grant_for(world, world.alice, **WINDOW)

    def attempt(_):
        for i in range(12):
            try:
                return world.authorize(g, world.alice, 10_000)
            except kernel.KernelBusy:
                time.sleep(0.15 * (i + 1))
        raise AssertionError("still busy after retries")

    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(attempt, range(8)))
    assert states(res).count("reserved") == 3
    assert {r["reason"] for r in res if r["state"] == "rejected"} <= {"VELOCITY_LIMIT_EXCEEDED"}
    world.check()


# ------------------------------------------------------------------ approval threshold

def test_amount_above_threshold_is_held_without_funds_then_approved(world):
    g = grant_for(world, world.alice, review_above=5_000)
    before = world.grant(g)
    held = world.authorize(g, world.alice, 8_000)
    assert held["state"] == "proposed" and held["review_reason"] == "ABOVE_THRESHOLD"
    after = world.grant(g)
    assert (after["available"], after["reserved"]) == (before["available"], 0)       # nothing reserved while waiting
    assert world.authorize(g, world.alice, 3_000)["state"] == "reserved"             # at or under the threshold passes
    done = kernel.review(world.pool, transaction_id=held["transaction_id"], actor=world.owner, approve=True)
    assert done["state"] == "reserved"
    assert world.tx(held["transaction_id"])["reserved_at"] is not None
    world.check()


def test_an_ancestor_threshold_binds_the_child(world):
    parent = grant_for(world, world.alice, 60_000, review_above=5_000)
    child = world.delegate(parent, world.bob, 30_000, actor=world.alice, scope=scope())["grant_id"]
    held = world.authorize(child, world.bob, 8_000)
    assert held["state"] == "proposed" and held["review_reason"] == "ABOVE_THRESHOLD"


def test_the_lowest_threshold_on_the_path_wins(world):
    parent = grant_for(world, world.alice, 60_000, review_above=9_000)
    child = world.delegate(parent, world.bob, 30_000, actor=world.alice, scope=scope(review_above=4_000))["grant_id"]
    assert world.authorize(child, world.bob, 5_000)["review_reason"] == "ABOVE_THRESHOLD"


def test_owner_is_exempt_from_the_threshold_but_not_from_the_caller_flag(world):
    root = world.grant(world.root)
    assert root["scope"].get("review_above") is None
    other = kernel.create_mandate(world.pool, owner_principal_id=world.owner, currency="USD", total=100_000,
                                  protected_reserve=0, expires_at=world.grant(world.root)["expires_at"],
                                  scope=scope(per_tx_limit=100_000, review_above=1_000))
    g = other["root_grant_id"]
    assert world.authorize(g, world.owner, 8_000)["state"] == "reserved"
    flagged = world.authorize(g, world.owner, 500, needs_review=True)
    assert flagged["state"] == "proposed" and flagged["review_reason"] == "CALLER_FLAGGED"


def test_approval_rechecks_the_window(world):
    g = grant_for(world, world.alice, window_limit=10_000, window_seconds=3600, review_above=5_000)
    held = world.authorize(g, world.alice, 8_000)
    assert held["state"] == "proposed"                                               # holds nothing, counts nothing
    assert world.authorize(g, world.alice, 5_000)["state"] == "reserved"
    done = kernel.review(world.pool, transaction_id=held["transaction_id"], actor=world.owner, approve=True)
    assert done["state"] == "rejected" and done["reason"] == "VELOCITY_LIMIT_EXCEEDED"
    world.check()


def test_replay_returns_the_stored_hold(world):
    g = grant_for(world, world.alice, review_above=5_000)
    first = world.authorize(g, world.alice, 8_000, key="k-hold")
    again = world.authorize(g, world.alice, 8_000, key="k-hold")
    assert again["replayed"] is True and again["transaction_id"] == first["transaction_id"]
    assert again["state"] == "proposed" and again["review_reason"] == "ABOVE_THRESHOLD"


# ------------------------------------------------------------------ scope validation and attenuation

@pytest.mark.parametrize("over", [
    {"window_limit": 30_000, "window_seconds": 3600},
    {"window_limit": 30_000, "window_seconds": 3600, "review_above": 0},
    {"review_above": 5_000},
])
def test_new_scope_fields_are_accepted(world, over):
    assert world.delegate(world.root, world.alice, 1_000, scope=scope(**over))["grant_id"]


@pytest.mark.parametrize("over", [
    {"window_limit": 30_000},                                      # half a window
    {"window_seconds": 3600},
    {"window_limit": 0, "window_seconds": 3600},
    {"window_limit": 5, "window_seconds": 10},                     # shorter than the 60 s minimum
    {"window_limit": 5, "window_seconds": 3600, "bogus": 1},       # unknown key
    {"review_above": -1},
    {"review_above": True},
])
def test_bad_new_scope_fields_are_rejected(world, over):
    with pytest.raises(kernel.ValidationFailed):
        world.delegate(world.root, world.alice, 1_000, scope=scope(**over))


@pytest.mark.parametrize("child", [
    {"window_limit": 40_000, "window_seconds": 3600},              # larger limit
    {"window_limit": 30_000, "window_seconds": 600},               # same cap over a shorter window is looser
    {"review_above": 9_000},                                       # higher threshold
])
def test_a_looser_child_control_is_refused(world, child):
    parent = grant_for(world, world.alice, 60_000, window_limit=30_000, window_seconds=3600, review_above=5_000)
    with pytest.raises(kernel.DelegationRejected) as exc:
        world.delegate(parent, world.bob, 10_000, actor=world.alice, scope=scope(**child))
    assert exc.value.code == "SCOPE_WIDER_THAN_PARENT"


@pytest.mark.parametrize("child", [
    {},                                                            # omitting is allowed; the ancestor still binds
    {"window_limit": 10_000, "window_seconds": 7200, "review_above": 1_000},
])
def test_a_stricter_or_silent_child_is_accepted(world, child):
    parent = grant_for(world, world.alice, 60_000, window_limit=30_000, window_seconds=3600, review_above=5_000)
    assert world.delegate(parent, world.bob, 10_000, actor=world.alice, scope=scope(**child))["grant_id"]


# ------------------------------------------------------------------ API read model

def test_state_endpoint_reports_window_use_and_review_reason(pool, world, monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "t")
    with TestClient(create_app(pool=pool)) as client:
        def person(kind):
            r = client.post("/admin/principals", json={"name": f"vt-{uuid.uuid4().hex[:6]}", "kind": kind},
                            headers={"X-Admin-Token": "t"}).json()
            return r["principal_id"], {"Authorization": f"Bearer {r['api_key']}"}
        owner_id, owner = person("human")
        agent_id, agent = person("agent")
        sc = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": True}
        m = client.post("/mandates", headers=owner, json={
            "currency": "USD", "total": 100_000, "protected_reserve": 0,
            "expires_at": world.grant(world.root)["expires_at"].isoformat(), "scope": sc}).json()
        g = client.post("/grants", headers=owner, json={
            "parent_grant_id": m["root_grant_id"], "holder_principal_id": agent_id, "amount": 50_000,
            "expires_at": world.grant(world.root)["expires_at"].isoformat(), "idempotency_key": uuid.uuid4().hex,
            "scope": {**sc, "can_delegate": False, "window_limit": 30_000, "window_seconds": 3600,
                      "review_above": 8_000}}).json()["grant_id"]
        ok = client.post("/transactions/authorize", headers=agent, json={
            "grant_id": g, "amount": 6_000, "currency": "USD", "recipient": "aws", "category": "cloud",
            "idempotency_key": uuid.uuid4().hex}).json()
        held = client.post("/transactions/authorize", headers=agent, json={
            "grant_id": g, "amount": 9_000, "currency": "USD", "recipient": "aws", "category": "cloud",
            "idempotency_key": uuid.uuid4().hex}).json()
        assert ok["state"] == "reserved" and held["review_reason"] == "ABOVE_THRESHOLD"
        st = client.get(f"/mandates/{m['mandate_id']}/state", headers=owner).json()
        mine = next(x for x in st["grants"] if x["id"] == g)
        assert mine["window_used"] == 6_000                                          # held proposals do not count
        assert "window_used" not in next(x for x in st["grants"] if x["id"] == m["root_grant_id"])
        assert {t["review_reason"] for t in st["transactions"] if t["state"] == "proposed"} == {"ABOVE_THRESHOLD"}
        assert st["invariants"]["ok"]
