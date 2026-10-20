"""Setup flow: a signed-in human creates agent principals and delegates to them (docs/plans/LOGIN_PLAN.md)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from budget_kernel.api.app import create_app
from budget_kernel.api.login import MAX_AGENTS
from budget_kernel.api.ratelimit import RateLimiter
from tests.integration.test_agent_flow import person

PW = "correct horse battery"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("BK_ALLOW_SIGNUP", "1")


@pytest.fixture
def client(pool):
    with TestClient(create_app(pool=pool, ratelimit=RateLimiter(0, 0, auth_per_min=0))) as c:
        yield c


def code(r):
    return r.json()["detail"]["code"]


def human(client, username):
    t = client.post("/auth/signup", json={"name": username, "username": username, "password": PW}).json()["session_token"]
    return {"Authorization": f"Bearer {t}"}


def test_a_human_creates_an_agent_and_gets_its_key_once(pool, client):
    me = human(client, "agent.maker")
    r = client.post("/agents", headers=me, json={"name": "Research bot"})
    assert r.status_code == 201
    body = r.json()
    assert body["api_key"].startswith("bk_") and body["name"] == "Research bot"
    agent = {"Authorization": f"Bearer {body['api_key']}"}
    who = client.get("/me", headers=agent).json()
    assert who["kind"] == "agent" and who["principal_id"] == body["principal_id"]
    with pool.connection() as c:
        row = c.execute("SELECT api_key_hash, password_hash, created_by FROM principals WHERE id = %s", (body["principal_id"],)).fetchone()
    assert row["api_key_hash"] and row["password_hash"] is None and row["created_by"] is not None
    assert body["api_key"] not in str(client.get("/agents", headers=me).json())      # never shown again


def test_only_a_human_can_create_agents(client):
    _, agent = person(client, "an.agent")
    r = client.post("/agents", headers=agent, json={"name": "child"})
    assert r.status_code == 403 and code(r) == "HUMAN_ONLY"
    assert client.post("/agents", json={"name": "anon"}).status_code == 401


def test_agent_creation_is_capped_per_person(client):
    me = human(client, "cap.tester")
    for i in range(MAX_AGENTS):
        assert client.post("/agents", headers=me, json={"name": f"bot {i}"}).status_code == 201
    r = client.post("/agents", headers=me, json={"name": "one too many"})
    assert r.status_code == 409 and code(r) == "AGENT_LIMIT"
    other = human(client, "cap.other")
    assert client.post("/agents", headers=other, json={"name": "fine"}).status_code == 201     # the cap is per person


def test_you_list_only_your_own_agents(client):
    a, b = human(client, "lister.a"), human(client, "lister.b")
    client.post("/agents", headers=a, json={"name": "mine"})
    client.post("/agents", headers=b, json={"name": "theirs"})
    names = [x["name"] for x in client.get("/agents", headers=a).json()["agents"]]
    assert names == ["mine"]


def test_an_agent_cannot_list_agents(client):
    _, agent = person(client, "peeker")
    assert client.get("/agents", headers=agent).status_code == 403


def test_setup_end_to_end_with_a_password_account(client):
    """Sign up, fund a mandate, create an agent, delegate to it, and the agent can ask: no admin token anywhere."""
    me = human(client, "full.setup")
    m = client.post("/mandates", headers=me, json={
        "currency": "USD", "total": 100_000, "protected_reserve": 10_000,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "scope": {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 50_000, "can_delegate": True}}).json()
    a = client.post("/agents", headers=me, json={"name": "Research bot"}).json()
    g = client.post("/grants", headers=me, json={
        "parent_grant_id": m["root_grant_id"], "holder_principal_id": a["principal_id"], "amount": 30_000,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "scope": {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": False},
        "idempotency_key": "setup-1"})
    assert g.status_code == 201
    agent = {"Authorization": f"Bearer {a['api_key']}"}
    d = client.post("/transactions/authorize", headers=agent, json={
        "grant_id": g.json()["grant_id"], "amount": 5_000, "currency": "USD", "recipient": "aws", "category": "cloud",
        "idempotency_key": "pay-1"})
    assert d.status_code == 200 and d.json()["state"] == "reserved"
    state = client.get(f"/mandates/{m['mandate_id']}/state", headers=me).json()
    assert state["invariants"]["ok"] is True
    audits = client.get(f"/mandates/{m['mandate_id']}/audit", headers=me).json()
    assert audits is not None


def test_agent_creation_is_audited_without_the_key(pool, client):
    me = human(client, "audited.maker")
    body = client.post("/agents", headers=me, json={"name": "audited bot"}).json()
    with pool.connection() as c:
        rows = c.execute("SELECT kind, detail::text AS d FROM audit_events WHERE subject_id = %s", (body["principal_id"],)).fetchall()
    assert [r["kind"] for r in rows] == ["AGENT_CREATED"]
    assert body["api_key"] not in rows[0]["d"]
