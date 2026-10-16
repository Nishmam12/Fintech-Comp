"""BK-412: key expiry, disabling, rotation (ADR-0009 C2)."""
import pytest
from fastapi.testclient import TestClient

from budget_kernel.api.app import create_app
from budget_kernel.api.ratelimit import RateLimiter
from tests.integration.test_agent_flow import HEADERS_ADMIN, person


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "test-admin-token")


@pytest.fixture
def client(pool):
    with TestClient(create_app(pool=pool, ratelimit=RateLimiter(0, 0))) as c:
        yield c


def code(r):
    return r.json()["detail"]["code"]


def test_expired_key_gets_key_expired_and_unknown_key_stays_unauthenticated(pool, client):
    pid, key = person(client, "short-lived")
    assert client.get("/me", headers=key).status_code == 200
    with pool.connection() as c:
        c.execute("UPDATE principals SET key_expires_at = clock_timestamp() - interval '1 second' WHERE id = %s", (pid,))
    r = client.get("/me", headers=key)
    assert r.status_code == 401 and code(r) == "KEY_EXPIRED"
    r = client.get("/me", headers={"Authorization": "Bearer bk_nope"})
    assert r.status_code == 401 and code(r) == "UNAUTHENTICATED"


def test_expires_in_days_sets_a_future_expiry_and_is_validated(client):
    r = client.post("/admin/principals", json={"name": "x", "kind": "agent", "expires_in_days": 7}, headers=HEADERS_ADMIN)
    assert r.status_code == 201 and r.json()["key_expires_at"]
    key = {"Authorization": f"Bearer {r.json()['api_key']}"}
    assert client.get("/me", headers=key).status_code == 200
    none = client.post("/admin/principals", json={"name": "y", "kind": "agent"}, headers=HEADERS_ADMIN).json()
    assert none["key_expires_at"] is None
    for bad in (0, 366, -1, 1.5, "7"):
        r = client.post("/admin/principals", json={"name": "z", "kind": "agent", "expires_in_days": bad}, headers=HEADERS_ADMIN)
        assert r.status_code == 422


def test_disabled_principal_gets_principal_disabled_and_disable_is_idempotent(pool, client):
    pid, key = person(client, "to-disable")
    r = client.post(f"/admin/principals/{pid}/disable", headers=HEADERS_ADMIN)
    assert r.status_code == 200 and r.json()["already"] is False
    r = client.get("/me", headers=key)
    assert r.status_code == 401 and code(r) == "PRINCIPAL_DISABLED"
    again = client.post(f"/admin/principals/{pid}/disable", headers=HEADERS_ADMIN)
    assert again.status_code == 200 and again.json()["already"] is True
    with pool.connection() as c:
        n = c.execute("SELECT count(*) AS n FROM audit_events WHERE kind = 'PRINCIPAL_DISABLED' AND subject_id = %s",
                      (pid,)).fetchone()["n"]
    assert n == 1                                            # the repeat did not add audit noise


def test_disable_needs_the_admin_token_and_a_real_principal(client):
    pid, key = person(client, "p")
    assert client.post(f"/admin/principals/{pid}/disable", headers=key).status_code == 403
    assert client.post(f"/admin/principals/{pid}/disable").status_code == 403
    r = client.post("/admin/principals/00000000-0000-0000-0000-000000000000/disable", headers=HEADERS_ADMIN)
    assert r.status_code == 404
    assert client.post("/admin/principals/not-a-uuid/disable", headers=HEADERS_ADMIN).status_code == 422


def test_disable_does_not_revoke_grants(pool, client):
    from tests.integration.test_agent_flow import setup
    owner, agent, mid, g = setup(client)
    holder = client.get("/me", headers=agent).json()["principal_id"]
    client.post(f"/admin/principals/{holder}/disable", headers=HEADERS_ADMIN)
    st = client.get(f"/mandates/{mid}/state", headers=owner).json()
    assert {x["status"] for x in st["grants"]} == {"active"}


def test_rotation_kills_the_old_key_and_the_new_one_works(client):
    _, old = person(client, "rot")
    r = client.post("/me/rotate-key", headers=old)
    assert r.status_code == 200
    new = {"Authorization": f"Bearer {r.json()['api_key']}"}
    assert client.get("/me", headers=old).status_code == 401
    assert client.get("/me", headers=new).status_code == 200


def test_rotating_twice_leaves_exactly_one_valid_key(pool, client):
    pid, k0 = person(client, "twice")
    k1 = {"Authorization": f"Bearer {client.post('/me/rotate-key', headers=k0).json()['api_key']}"}
    k2 = {"Authorization": f"Bearer {client.post('/me/rotate-key', headers=k1).json()['api_key']}"}
    assert [client.get("/me", headers=k).status_code for k in (k0, k1, k2)] == [401, 401, 200]
    with pool.connection() as c:
        assert c.execute("SELECT key_rotated_at IS NOT NULL AS r FROM principals WHERE id = %s", (pid,)).fetchone()["r"]


def test_rotation_keeps_expiry_and_audit_rows_hold_no_key_material(pool, client):
    r = client.post("/admin/principals", json={"name": "aud", "kind": "agent", "expires_in_days": 30}, headers=HEADERS_ADMIN).json()
    first = r["api_key"]
    rot = client.post("/me/rotate-key", headers={"Authorization": f"Bearer {first}"}).json()
    assert rot["key_expires_at"] == r["key_expires_at"]
    with pool.connection() as c:
        rows = c.execute("SELECT actor_principal_id, subject_id, mandate_id, detail::text AS d FROM audit_events"
                         " WHERE kind = 'KEY_ROTATED' AND subject_id = %s", (r["principal_id"],)).fetchall()
        dump = c.execute("SELECT string_agg(a::text, ' ') AS t FROM audit_events a").fetchone()["t"]
    assert len(rows) == 1 and rows[0]["mandate_id"] is None
    from budget_kernel.api.auth import hash_key
    for secret in (first, rot["api_key"], hash_key(first), hash_key(rot["api_key"])):
        assert secret not in dump


def test_rotate_requires_authentication(client):
    assert client.post("/me/rotate-key").status_code == 401
