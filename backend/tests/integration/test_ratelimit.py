"""BK-411: HTTP rate limiting (ADR-0009 C1). The clock is injected; nothing sleeps."""
import pytest
from fastapi.testclient import TestClient

from budget_kernel.api.app import create_app
from budget_kernel.api.ratelimit import RateLimiter
from tests.integration.test_agent_flow import HEADERS_ADMIN, person, setup  # noqa: F401
from tests.integration.test_interpret import Fake


class Clock:
    t = 5000.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def env(monkeypatch, pool):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k2")
    with pool.connection() as c:
        c.execute("TRUNCATE budget_buckets, inference_calls CASCADE")


def client_with(pool, default=1000, model=1000, clock=None, trust_proxy=False, fake=None):
    rl = RateLimiter(default, model, clock=clock or Clock(), trust_proxy=trust_proxy)
    return TestClient(create_app(pool=pool, llm_transport=(fake or Fake()).transport, ratelimit=rl)), rl


def test_burst_gets_429_with_retry_after_then_recovers(pool):
    clock = Clock()
    client, _ = client_with(pool, default=3, clock=clock)
    with client:
        _, key = person(client, "a")                                 # 1 request (admin, by IP)
        ok = [client.get("/me", headers=key).status_code for _ in range(2)]
        assert ok == [200, 200]
        r = client.get("/me", headers=key)
        assert r.status_code == 200
        r = client.get("/me", headers=key)
        assert r.status_code == 429
        assert r.json() == {"detail": {"code": "RATE_LIMITED", "message": r.json()["detail"]["message"]}}
        wait = int(r.headers["Retry-After"])
        assert wait == 20                                            # 3 per minute: one token per 20 s
        clock.t += wait
        assert client.get("/me", headers=key).status_code == 200


def test_two_principals_do_not_share_a_bucket(pool):
    client, _ = client_with(pool, default=2)
    with client:
        _, a = person(client, "a")
        _, b = person(client, "b")
        assert [client.get("/me", headers=a).status_code for _ in range(3)] == [200, 200, 429]
        assert client.get("/me", headers=b).status_code == 200


def test_model_endpoints_have_their_own_smaller_bucket(pool):
    client, _ = client_with(pool, default=1000, model=2)
    with client:
        owner, agent, _, g = setup(client)
        body = {"grant_id": g, "text": "Pay $1.00 to AWS for cloud"}
        codes = [client.post("/agent/request", headers=agent, json={**body, "idempotency_key": f"k{i}"}).status_code
                 for i in range(3)]
        assert codes == [200, 200, 429]
        assert client.post("/interpret", headers=agent, json=body).status_code == 429     # shared model bucket
        assert client.get("/me", headers=agent).status_code == 200                        # ordinary calls unaffected
        assert client.post("/interpret", headers=owner, json=body).status_code != 429     # other principal unaffected


def test_health_is_never_limited(pool):
    client, _ = client_with(pool, default=1)
    with client:
        assert all(client.get("/health").status_code == 200 for _ in range(20))


def test_unauthenticated_and_bad_keys_share_the_ip_bucket(pool):
    client, rl = client_with(pool, default=3)
    with client:
        codes = [client.get("/me", headers={"Authorization": f"Bearer bk_garbage{i}"}).status_code for i in range(5)]
        assert codes == [401, 401, 401, 429, 429]                    # rotating garbage keys does not buy new buckets
        assert len(rl) == 1


def test_x_forwarded_for_is_ignored_unless_trusted(pool):
    client, _ = client_with(pool, default=2)
    with client:
        codes = [client.get("/me", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(3)]
        assert codes == [401, 401, 429]                              # spoofing a new address does not reset the limit
    client, _ = client_with(pool, default=2, trust_proxy=True)
    with client:
        codes = [client.get("/me", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(3)]
        assert codes == [401, 401, 401]                              # behind a trusted proxy each client has its own bucket


def test_retry_after_is_readable_by_the_browser(pool):
    client, _ = client_with(pool, default=1)
    with client:
        h = {"Origin": "http://localhost:3000"}
        client.get("/me", headers=h)
        r = client.get("/me", headers=h)
        assert r.status_code == 429 and r.headers["access-control-expose-headers"] == "Retry-After"
        assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
