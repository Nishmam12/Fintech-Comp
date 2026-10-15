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

        assert client.get("/me", headers=owner).json() == {"principal_id": owner_id, "name": client.get("/me", headers=owner).json()["name"], "kind": "human"}
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
