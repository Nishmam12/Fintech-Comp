"""Attack scenarios: the unsafe baseline must actually fail, the kernel must actually hold."""
import pytest
from fastapi.testclient import TestClient

from budget_kernel import simulation
from budget_kernel.api.app import create_app


def test_concurrent_overspend_breaks_the_baseline_but_not_the_kernel(pool):
    r = simulation.run(pool, "concurrency_overspend")
    assert r["naive"]["violated"] is True and r["naive"]["metrics"]["spent_total"] > 90_000
    assert r["naive"]["metrics"]["lowest_balance"] < 0
    assert r["kernel"]["violated"] is False and r["kernel"]["metrics"]["approved"] == 3
    assert r["kernel"]["metrics"]["gave_up"] == 0          # safe AND live: nobody was refused for being busy
    assert r["kernel"]["metrics"]["invariant_violations"] == []


def test_delegation_amplification_breaks_the_baseline_but_not_the_kernel(pool):
    r = simulation.run(pool, "delegation_amplification")
    assert r["naive"]["violated"] is True and r["naive"]["metrics"]["delegated_total"] > 90_000
    assert r["kernel"]["violated"] is False and r["kernel"]["metrics"]["children_created"] == 3
    assert r["kernel"]["metrics"]["rejected"] == 3 and r["kernel"]["metrics"]["gave_up"] == 0


def test_revoked_ancestor_is_honoured_only_by_the_kernel(pool):
    r = simulation.run(pool, "revoked_ancestor")
    assert r["naive"]["violated"] is True
    assert r["kernel"]["violated"] is False and r["kernel"]["metrics"]["reason"] == "GRANT_REVOKED"


def test_revocation_race_leaves_no_live_authority_in_the_kernel(pool):
    r = simulation.run(pool, "revocation_race")          # baseline outcome is timing-dependent: reported, not asserted
    assert r["kernel"]["violated"] is False
    assert r["kernel"]["metrics"]["live_reservations_on_revoked_grant"] == 0
    assert r["kernel"]["metrics"]["grant_available"] == 0


def test_duplicate_delivery_double_debits_the_baseline_only(pool):
    r = simulation.run(pool, "replay_duplicate")
    assert r["naive"]["violated"] is True and r["naive"]["metrics"]["debits"] > 1
    assert r["kernel"]["violated"] is False and r["kernel"]["metrics"]["transactions_created"] == 1


def test_split_purchase_limitation_is_reported_honestly(pool):
    r = simulation.run(pool, "split_purchases")
    assert r["informational"] is True and r["kernel"]["informational_finding"] is True
    m = r["kernel"]["metrics"]
    assert m["single_large_request"] == "PER_TX_LIMIT_EXCEEDED"
    assert m["split_requests_approved"] == 5 and m["split_total"] == 50_000      # bounded by the grant balance
    assert "not a velocity limit" in r["kernel"]["summary"] and "but 5 requests" in r["kernel"]["summary"]
    assert m["windowed_requests_approved"] == 2 and m["windowed_total"] == 20_000      # ADR-0008 stops the split
    assert m["windowed_refusal"] == "VELOCITY_LIMIT_EXCEEDED" and r["kernel"]["violated"] is False


def test_a_probing_agent_is_contained_by_the_kernel_only(pool):
    r = simulation.run(pool, "limit_probing")
    n, m = r["naive"]["metrics"], r["kernel"]["metrics"]
    assert r["naive"]["violated"] is True and n["probes_refused"] == n["probes_sent"] and n["contained"] is False
    assert n["valid_request_after_probing"] == "processed"
    assert r["kernel"]["violated"] is False and m["contained"] is True
    assert m["suspended_after_probe"] == 5 and m["strikes"] == 5
    assert m["refusals_by_reason"] == {"CATEGORY_NOT_ALLOWED": 5, "GRANT_SUSPENDED": m["probes_sent"] - 5}
    assert m["valid_request_while_suspended"] == "GRANT_SUSPENDED" and m["valid_request_after_reinstate"] == "reserved"
    assert m["invariant_violations"] == []


def test_only_one_simulation_runs_at_a_time():
    from budget_kernel import kernel
    from budget_kernel.simulation import scenarios
    assert scenarios._RUNNING.acquire(blocking=False)
    try:
        with pytest.raises(kernel.Conflict) as exc:
            simulation.run(None, "revoked_ancestor")         # refused before touching the pool
        assert exc.value.code == "SIMULATION_RUNNING"
    finally:
        scenarios._RUNNING.release()


def test_simulation_api_is_human_only_and_validates_names(pool, monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "t")
    with TestClient(create_app(pool=pool)) as client:
        def person(kind):
            r = client.post("/admin/principals", json={"name": f"sim-{kind}", "kind": kind}, headers={"X-Admin-Token": "t"}).json()
            return {"Authorization": f"Bearer {r['api_key']}"}
        human, agent = person("human"), person("agent")
        assert client.get("/simulation/scenarios", headers=agent).json()["scenarios"] == sorted(simulation.SCENARIOS)
        assert client.post("/simulation/run", headers=agent, json={"scenario": "revoked_ancestor"}).status_code == 403
        assert client.post("/simulation/run", headers=human, json={"scenario": "nope"}).status_code == 404
        r = client.post("/simulation/run", headers=human, json={"scenario": "revoked_ancestor"})
        assert r.status_code == 200 and r.json()["naive"]["violated"] and not r.json()["kernel"]["violated"]
