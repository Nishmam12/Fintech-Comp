"""End-to-end through HTTP: auth, strict parsing, kernel decisions, error mapping, read models."""
import uuid

import pytest
from fastapi.testclient import TestClient

from budget_kernel.api.app import create_app
from tests.conftest import future, scope


@pytest.fixture()
def client(pool, monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "test-admin-token")
    with TestClient(create_app(pool=pool)) as c:
        yield c


def principal(client, name, kind="agent"):
    r = client.post("/admin/principals", json={"name": name, "kind": kind},
                    headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["principal_id"], {"Authorization": f"Bearer {body['api_key']}"}


def mandate(client, h):
    r = client.post("/mandates", headers=h, json={
        "currency": "USD", "total": 100_000, "protected_reserve": 10_000,
        "expires_at": future(30).isoformat(), "scope": scope(per_tx_limit=100_000)})
    assert r.status_code == 201, r.text
    return r.json()


def test_requires_api_key(client):
    assert client.post("/mandates", json={}).status_code == 401
    assert client.post("/mandates", json={}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_agent_cannot_create_a_mandate_via_api(client):
    _, agent = principal(client, "rogue-agent", "agent")
    r = client.post("/mandates", headers=agent, json={
        "currency": "USD", "total": 1_000_000, "protected_reserve": 0,
        "expires_at": future(30).isoformat(), "scope": scope()})
    assert (r.status_code, r.json()["code"]) == (403, "OWNER_MUST_BE_HUMAN")


def test_admin_token_required_for_principals(client):
    assert client.post("/admin/principals", json={"name": "x", "kind": "agent"}).status_code == 403


def test_end_to_end_delegate_authorize_settle_and_state(client):
    _, owner = principal(client, "owner", "human")
    alice_id, alice = principal(client, "alice")
    m = mandate(client, owner)
    r = client.post("/grants", headers=owner, json={
        "parent_grant_id": m["root_grant_id"], "holder_principal_id": alice_id, "amount": 30_000,
        "expires_at": future(10).isoformat(), "scope": scope(per_tx_limit=20_000, can_delegate=False),
        "idempotency_key": "g1"})
    assert r.status_code == 201, r.text
    child = r.json()["grant_id"]

    r = client.post("/transactions/authorize", headers=alice, json={
        "grant_id": child, "amount": 12_500, "currency": "USD", "recipient": "aws", "category": "cloud",
        "idempotency_key": "t1"})
    assert r.status_code == 200 and r.json()["state"] == "reserved", r.text
    tx = r.json()["transaction_id"]

    assert client.post(f"/transactions/{tx}/settle", headers=alice).status_code == 403   # agents cannot settle
    r = client.post(f"/transactions/{tx}/settle", headers=owner)
    assert r.status_code == 200 and r.json()["state"] == "settled", r.text

    s = client.get(f"/mandates/{m['mandate_id']}/state", headers=alice).json()
    assert s["invariants"]["ok"] is True
    g = {x["id"]: x for x in s["grants"]}[child]
    assert (g["available"], g["reserved"], g["settled"]) == (17_500, 0, 12_500)
    kinds = [e["kind"] for e in client.get(f"/mandates/{m['mandate_id']}/audit", headers=owner).json()["events"]]
    assert kinds[:1] == ["MANDATE_CREATED"] and "TX_SETTLED" in kinds


@pytest.mark.parametrize("smuggled", [{"authorized": True}, {"state": "reserved"}, {"reserved": 0}])
def test_trusted_fields_cannot_be_smuggled_into_requests(client, smuggled):
    _, owner = principal(client, "owner", "human")
    m = mandate(client, owner)
    body = {"grant_id": m["root_grant_id"], "amount": 100, "currency": "USD", "recipient": "aws",
            "category": "cloud", "idempotency_key": uuid.uuid4().hex, **smuggled}
    r = client.post("/transactions/authorize", headers=owner, json=body)
    assert r.status_code == 422


@pytest.mark.parametrize("amount", [1.5, "100", True, -1, 0])
def test_amounts_must_be_positive_integers(client, amount):
    _, owner = principal(client, "owner", "human")
    m = mandate(client, owner)
    r = client.post("/transactions/authorize", headers=owner, json={
        "grant_id": m["root_grant_id"], "amount": amount, "currency": "USD", "recipient": "aws",
        "category": "cloud", "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 422


def test_kernel_errors_map_to_http_codes(client):
    _, owner = principal(client, "owner", "human")
    bob_id, bob = principal(client, "bob")
    m = mandate(client, owner)
    base = {"grant_id": m["root_grant_id"], "amount": 100, "currency": "USD", "recipient": "aws",
            "category": "cloud", "idempotency_key": "same"}
    assert client.post("/transactions/authorize", headers=bob, json=base).status_code == 403     # not holder
    assert client.post("/transactions/authorize", headers=owner, json=base).status_code == 200
    r = client.post("/transactions/authorize", headers=owner, json={**base, "amount": 200})       # key reuse
    assert (r.status_code, r.json()["code"]) == (409, "IDEMPOTENCY_CONFLICT")
    assert client.get(f"/mandates/{m['mandate_id']}/state", headers=bob).status_code == 403       # not a participant
    assert client.post(f"/grants/{uuid.uuid4()}/revoke", headers=owner).status_code == 404
    assert client.post("/grants/not-a-uuid/revoke", headers=owner).status_code == 422


def test_revoke_via_api_reports_in_flight_exposure(client):
    _, owner = principal(client, "owner", "human")
    alice_id, alice = principal(client, "alice")
    svc_id, svc = principal(client, "settler", "service")
    m = mandate(client, owner)
    child = client.post("/grants", headers=owner, json={
        "parent_grant_id": m["root_grant_id"], "holder_principal_id": alice_id, "amount": 30_000,
        "expires_at": future(10).isoformat(), "scope": scope(), "idempotency_key": "g"}).json()["grant_id"]
    tx = client.post("/transactions/authorize", headers=alice, json={
        "grant_id": child, "amount": 10_000, "currency": "USD", "recipient": "aws", "category": "cloud",
        "idempotency_key": "t"}).json()["transaction_id"]
    r = client.post(f"/grants/{child}/revoke", headers=owner)
    assert r.status_code == 200 and r.json()["reclaimed"] == 30_000
    r = client.post(f"/transactions/{tx}/settle", headers=svc)
    assert r.status_code == 409          # reservation was released by the revoke
