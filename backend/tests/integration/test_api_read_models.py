"""Read models the dashboard needs: GET /me, GET /mandates, and the stored proposal in the state."""
import uuid

from fastapi.testclient import TestClient

from budget_kernel.api.app import create_app
from tests.conftest import future


def test_whoami_mandate_list_and_proposal_in_state(pool, monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "t")
    with TestClient(create_app(pool=pool)) as client:
        def person(kind):
            r = client.post("/admin/principals", json={"name": f"rm-{uuid.uuid4().hex[:6]}", "kind": kind},
                            headers={"X-Admin-Token": "t"}).json()
            return r["principal_id"], {"Authorization": f"Bearer {r['api_key']}"}
        owner_id, owner = person("human")
        agent_id, agent = person("agent")
        _, stranger = person("agent")

        assert client.get("/me", headers=owner).json() == {"principal_id": owner_id, "name": client.get("/me", headers=owner).json()["name"], "kind": "human", "username": None}
        assert client.get("/me").status_code == 401

        sc = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": True}
        exp = future(10).isoformat()
        m = client.post("/mandates", headers=owner, json={"currency": "USD", "total": 100_000, "protected_reserve": 0,
                                                          "expires_at": exp, "scope": sc}).json()
        g = client.post("/grants", headers=owner, json={
            "parent_grant_id": m["root_grant_id"], "holder_principal_id": agent_id, "amount": 40_000, "expires_at": exp,
            "idempotency_key": uuid.uuid4().hex, "scope": {**sc, "can_delegate": False, "review_above": 1_000}}).json()["grant_id"]

        mine = {x["id"]: x for x in client.get("/mandates", headers=owner).json()["mandates"]}
        assert mine[m["mandate_id"]]["role"] == "owner"
        theirs = {x["id"]: x for x in client.get("/mandates", headers=agent).json()["mandates"]}
        assert theirs[m["mandate_id"]]["role"] == "holder"
        assert m["mandate_id"] not in {x["id"] for x in client.get("/mandates", headers=stranger).json()["mandates"]}

        # a held request keeps its (untrusted) proposal in the state, so the approval inbox can show the model trail
        held = client.post("/agent/request", headers=agent, json={
            "grant_id": g, "text": "pay 50 USD to aws for cloud", "idempotency_key": uuid.uuid4().hex}).json()
        assert held["decision"]["state"] == "proposed"
        st = client.get(f"/mandates/{m['mandate_id']}/state", headers=owner).json()
        tx = next(t for t in st["transactions"] if t["id"] == held["decision"]["transaction_id"])
        assert tx["proposal"]["amount_minor"] == 5_000 and tx["review_reason"] == "ABOVE_THRESHOLD"


def test_names_in_state_audit_and_budget(pool, monkeypatch):
    """BK-501: names are added to the read models; ids stay, nothing is removed, a missing principal is null/fallback."""
    monkeypatch.setenv("BK_ADMIN_TOKEN", "t")
    with TestClient(create_app(pool=pool)) as client:
        def person(name, kind):
            r = client.post("/admin/principals", json={"name": name, "kind": kind}, headers={"X-Admin-Token": "t"}).json()
            return r["principal_id"], {"Authorization": f"Bearer {r['api_key']}"}
        owner_id, owner = person("Nabil", "human")
        bot_id, _ = person("Research bot", "agent")
        sc = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": True}
        exp = future(10).isoformat()
        m = client.post("/mandates", headers=owner, json={"currency": "USD", "total": 100_000, "protected_reserve": 0,
                                                          "expires_at": exp, "scope": sc}).json()
        client.post("/grants", headers=owner, json={
            "parent_grant_id": m["root_grant_id"], "holder_principal_id": bot_id, "amount": 40_000, "expires_at": exp,
            "idempotency_key": uuid.uuid4().hex, "scope": {**sc, "can_delegate": False}})

        st = client.get(f"/mandates/{m['mandate_id']}/state", headers=owner).json()
        assert st["mandate"]["owner_name"] == "Nabil" and st["mandate"]["owner_principal_id"] == owner_id
        assert {g["holder_name"]: g["holder_principal_id"] for g in st["grants"]}["Research bot"] == bot_id
        assert {"available", "reserved", "settled", "strikes_in_window"} <= set(st["grants"][0])

        ev = client.get(f"/mandates/{m['mandate_id']}/audit", headers=owner).json()["events"]
        assert any(e["actor_name"] == "Nabil" and e["actor_principal_id"] == owner_id for e in ev)
        assert all("actor_name" in e for e in ev)

        ghost = str(uuid.uuid4())
        with pool.connection() as c:
            c.execute("INSERT INTO budget_buckets (month, bucket, cap_micro_usd) VALUES"
                      " (date_trunc('month', now() AT TIME ZONE 'UTC')::date, %s, 1), (date_trunc('month', now() AT TIME ZONE 'UTC')::date, %s, 1)"
                      " ON CONFLICT DO NOTHING", (f"principal:{bot_id}", f"principal:{ghost}"))
        b = {x["bucket"]: x for x in client.get("/budget", headers=owner).json()["buckets"]}
        assert b[f"principal:{bot_id}"]["label"] == "Research bot"
        assert b[f"principal:{ghost}"]["label"] == f"principal:{ghost}"      # unknown principal: no error, falls back
        assert all("cap_micro_usd" in x and "label" in x for x in b.values())
