"""Username and password login, sessions, sign-up, password change (docs/plans/LOGIN_PLAN.md).

A session token resolves to the same Principal as an API key, so the point of these tests is who can obtain a credential and
what happens to it: lockout, expiry, revocation, disabling, and that nothing secret is written down."""
import pytest
from fastapi.testclient import TestClient
from psycopg.errors import CheckViolation

from budget_kernel.api.app import create_app
from budget_kernel.api.passwords import hash_password, verify_password
from budget_kernel.api.ratelimit import RateLimiter
from tests.integration.test_agent_flow import HEADERS_ADMIN, person

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


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, username, password=PW, name="Pat"):
    return client.post("/auth/signup", json={"name": name, "username": username, "password": password})


def login(client, username, password=PW):
    return client.post("/auth/login", json={"username": username, "password": password})


# ------------------------------------------------------------------------------------------------ hashing

def test_password_hash_round_trip_and_format():
    h = hash_password(PW)
    assert h.startswith("scrypt$") and PW not in h
    assert verify_password(PW, h) and not verify_password(PW + "x", h)
    assert hash_password(PW) != h                       # a fresh salt every time
    assert not verify_password(PW, "garbage") and not verify_password(PW, "scrypt$1$2$3$zz$zz")


# ------------------------------------------------------------------------------------------------ sign-up

def test_signup_is_off_unless_enabled(client, monkeypatch):
    monkeypatch.delenv("BK_ALLOW_SIGNUP")
    r = signup(client, "nosignup")
    assert r.status_code == 403 and code(r) == "SIGNUP_DISABLED"
    assert client.get("/auth/config").json() == {"signup": False}
    monkeypatch.setenv("BK_ALLOW_SIGNUP", "1")
    assert client.get("/auth/config").json() == {"signup": True}


def test_signup_creates_a_human_with_a_working_session(pool, client):
    r = signup(client, "Alice.Smith")
    assert r.status_code == 201
    body = r.json()
    assert body["session_token"].startswith("bks_") and body["expires_at"]
    me = client.get("/me", headers=bearer(body["session_token"])).json()
    assert me["kind"] == "human" and me["name"] == "Pat" and me["username"] == "alice.smith"
    with pool.connection() as c:
        row = c.execute("SELECT username, password_hash, api_key_hash FROM principals WHERE id = %s", (me["principal_id"],)).fetchone()
    assert row["username"] == "alice.smith" and row["password_hash"].startswith("scrypt$") and PW not in row["password_hash"]
    assert row["api_key_hash"] is None                   # a password person has no API key until they ask for one


def test_username_is_unique_case_insensitively(client):
    assert signup(client, "dupe.user").status_code == 201
    r = signup(client, "DUPE.User")
    assert r.status_code == 409 and code(r) == "USERNAME_TAKEN"


@pytest.mark.parametrize("bad", ["ab", "has space", "-leading", "x" * 70, "semi;colon", "émile", ""])
def test_bad_usernames_are_refused(client, bad):
    r = signup(client, bad)
    assert r.status_code in (400, 422)


@pytest.mark.parametrize("pw", ["short", "1234567", "x" * 129])
def test_weak_passwords_are_refused(client, pw):
    r = signup(client, "weakling", password=pw)
    assert r.status_code in (400, 422)
    assert login(client, "weakling", pw).status_code == 401      # and nothing was created




def test_passwords_are_not_trimmed(client):
    assert signup(client, "spacey.pw", password="  spaced out pass  ").status_code == 201
    assert login(client, "spacey.pw", "  spaced out pass  ").status_code == 200
    assert login(client, "spacey.pw", "spaced out pass").status_code == 401


# ------------------------------------------------------------------------------------------------ login

def test_wrong_password_and_unknown_user_look_the_same(client):
    signup(client, "known.user")
    wrong = login(client, "known.user", "not the password")
    unknown = login(client, "nobody.here", "not the password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() and code(wrong) == "INVALID_CREDENTIALS"


def test_login_returns_a_session_that_works_and_each_login_is_its_own_session(client):
    signup(client, "multi.login")
    a, b = login(client, "multi.login").json(), login(client, "multi.login").json()
    assert a["session_token"] != b["session_token"]
    for t in (a, b):
        assert client.get("/me", headers=bearer(t["session_token"])).status_code == 200


def test_five_failures_lock_the_account_and_the_lock_looks_like_a_wrong_password(pool, client):
    signup(client, "lock.me")
    for _ in range(5):
        assert login(client, "lock.me", "wrong wrong wrong").status_code == 401
    locked = login(client, "lock.me")                    # the right password, but the account is locked
    assert locked.status_code == 401 and code(locked) == "INVALID_CREDENTIALS"
    with pool.connection() as c:                         # a failed attempt while locked does not extend the lock
        before = c.execute("SELECT locked_until FROM principals WHERE username = 'lock.me'").fetchone()["locked_until"]
    login(client, "lock.me", "wrong wrong wrong")
    with pool.connection() as c:
        after = c.execute("SELECT locked_until FROM principals WHERE username = 'lock.me'").fetchone()["locked_until"]
        c.execute("UPDATE principals SET locked_until = clock_timestamp() - interval '1 second' WHERE username = 'lock.me'")
    assert before == after
    assert login(client, "lock.me").status_code == 200   # the lock expired
    with pool.connection() as c:
        row = c.execute("SELECT failed_logins, locked_until FROM principals WHERE username = 'lock.me'").fetchone()
    assert row["failed_logins"] == 0 and row["locked_until"] is None


def test_success_resets_the_failure_count(pool, client):
    signup(client, "reset.count")
    for _ in range(3):
        login(client, "reset.count", "wrong wrong wrong")
    assert login(client, "reset.count").status_code == 200
    with pool.connection() as c:
        assert c.execute("SELECT failed_logins FROM principals WHERE username = 'reset.count'").fetchone()["failed_logins"] == 0


def test_a_disabled_person_cannot_log_in_and_existing_sessions_stop(pool, client):
    t = signup(client, "to.disable").json()["session_token"]
    pid = client.get("/me", headers=bearer(t)).json()["principal_id"]
    client.post(f"/admin/principals/{pid}/disable", headers=HEADERS_ADMIN)
    r = client.get("/me", headers=bearer(t))
    assert r.status_code == 401 and code(r) == "PRINCIPAL_DISABLED"
    again = login(client, "to.disable")
    assert again.status_code == 401 and code(again) == "INVALID_CREDENTIALS"      # does not say the account exists


def test_an_agent_cannot_have_a_password_or_log_in(pool, client):
    aid, key = person(client, "robot")
    assert login(client, "robot", PW).status_code == 401
    with pool.connection() as c, pytest.raises(CheckViolation):
        c.execute("UPDATE principals SET username = 'robot.user', password_hash = %s WHERE id = %s", (hash_password(PW), aid))


# ------------------------------------------------------------------------------------------------ sessions

def test_expired_and_revoked_sessions_are_refused(pool, client):
    signup(client, "short.life")
    t = login(client, "short.life").json()["session_token"]
    assert client.get("/me", headers=bearer(t)).status_code == 200
    with pool.connection() as c:
        c.execute("UPDATE sessions SET expires_at = clock_timestamp() - interval '1 second' WHERE principal_id ="
                  " (SELECT id FROM principals WHERE username = 'short.life')")
    r = client.get("/me", headers=bearer(t))
    assert r.status_code == 401 and code(r) == "SESSION_EXPIRED"
    t2 = login(client, "short.life").json()["session_token"]
    assert client.post("/auth/logout", headers=bearer(t2)).status_code == 200
    r = client.get("/me", headers=bearer(t2))
    assert r.status_code == 401 and code(r) == "SESSION_EXPIRED"


def test_logout_revokes_only_that_session(client):
    signup(client, "two.tabs")
    a = login(client, "two.tabs").json()["session_token"]
    b = login(client, "two.tabs").json()["session_token"]
    client.post("/auth/logout", headers=bearer(a))
    assert client.get("/me", headers=bearer(a)).status_code == 401
    assert client.get("/me", headers=bearer(b)).status_code == 200


def test_logout_needs_a_session_and_an_api_key_cannot_log_out(client):
    assert client.post("/auth/logout").status_code == 401
    _, key = person(client, "keyed.human", "human")
    r = client.post("/auth/logout", headers=key)
    assert r.status_code == 400 and code(r) == "NOT_A_SESSION"


def test_a_session_is_not_an_admin_token_and_api_keys_still_work(client):
    t = signup(client, "not.admin").json()["session_token"]
    r = client.post("/admin/principals", json={"name": "x", "kind": "agent"}, headers=bearer(t))
    assert r.status_code == 403 and code(r) == "ADMIN_ONLY"
    _, key = person(client, "still.keyed")
    assert client.get("/me", headers=key).status_code == 200


def test_a_session_cannot_rotate_a_key_it_does_not_have(client):
    t = signup(client, "no.key").json()["session_token"]
    r = client.post("/me/rotate-key", headers=bearer(t))
    assert r.status_code == 400 and code(r) == "SESSION_HAS_NO_KEY"


def test_session_token_is_stored_hashed(pool, client):
    t = signup(client, "hashed.token").json()["session_token"]
    with pool.connection() as c:
        hashes = [r["token_hash"] for r in c.execute("SELECT token_hash FROM sessions").fetchall()]
    assert t not in hashes and all(len(h) == 64 for h in hashes)


def test_a_session_can_drive_the_kernel_like_a_key(client):
    """The whole point: a person who logs in with a password can create a mandate, same as one holding a key."""
    from datetime import datetime, timedelta, timezone
    t = signup(client, "can.fund").json()["session_token"]
    r = client.post("/mandates", headers=bearer(t), json={
        "currency": "USD", "total": 100_000, "protected_reserve": 10_000,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "scope": {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 50_000, "can_delegate": True}})
    assert r.status_code == 201
    mine = client.get("/mandates", headers=bearer(t)).json()["mandates"]
    assert any(m["id"] == r.json()["mandate_id"] and m["role"] == "owner" for m in mine)


# ------------------------------------------------------------------------------------------------ password change

def test_password_change_needs_the_current_password_and_revokes_the_other_sessions(client):
    signup(client, "change.me")
    here = login(client, "change.me").json()["session_token"]
    other = login(client, "change.me").json()["session_token"]
    bad = client.post("/me/password", headers=bearer(here), json={"current_password": "wrong wrong wrong", "new_password": "a brand new passphrase"})
    assert bad.status_code == 401 and code(bad) == "INVALID_CREDENTIALS"
    assert client.get("/me", headers=bearer(here)).status_code == 200       # a wrong attempt does not log you out
    weak = client.post("/me/password", headers=bearer(here), json={"current_password": PW, "new_password": "short"})
    assert weak.status_code in (400, 422)
    ok = client.post("/me/password", headers=bearer(here), json={"current_password": PW, "new_password": "a brand new passphrase"})
    assert ok.status_code == 200
    assert client.get("/me", headers=bearer(here)).status_code == 200       # this session stays
    assert client.get("/me", headers=bearer(other)).status_code == 401      # every other one is gone
    assert login(client, "change.me", PW).status_code == 401
    assert login(client, "change.me", "a brand new passphrase").status_code == 200


def test_password_change_is_for_password_accounts(client):
    _, key = person(client, "keyed.only", "human")
    r = client.post("/me/password", headers=key, json={"current_password": PW, "new_password": "a brand new passphrase"})
    assert r.status_code == 400 and code(r) == "NO_PASSWORD_SET"


# ------------------------------------------------------------------------------------------------ throttle

def test_login_attempts_are_throttled_per_client(pool):
    with TestClient(create_app(pool=pool, ratelimit=RateLimiter(0, 0, auth_per_min=3))) as c:
        for _ in range(3):
            assert login(c, "nobody.at.all", "whatever whatever").status_code == 401
        r = login(c, "nobody.at.all", "whatever whatever")
        assert r.status_code == 429 and code(r) == "RATE_LIMITED" and int(r.headers["retry-after"]) >= 1
        assert c.get("/health").status_code == 200


# ------------------------------------------------------------------------------------------------ nothing secret is written down

def test_no_password_hash_or_token_reaches_audit_or_errors(pool, client):
    token = signup(client, "quiet.user", password="a very quiet passphrase").json()["session_token"]
    login(client, "quiet.user", "a very quiet passphrase")
    client.post("/me/password", headers=bearer(token), json={"current_password": "a very quiet passphrase", "new_password": "another quiet passphrase"})
    bad = login(client, "quiet.user", "guess guess guess")
    with pool.connection() as c:
        pid = c.execute("SELECT id FROM principals WHERE username = 'quiet.user'").fetchone()["id"]
        rows = c.execute("SELECT kind, detail::text AS d FROM audit_events WHERE subject_id = %s OR actor_principal_id = %s", (pid, pid)).fetchall()
        stored = c.execute("SELECT password_hash FROM principals WHERE id = %s", (pid,)).fetchone()["password_hash"]
    kinds = {r["kind"] for r in rows}
    assert {"ACCOUNT_CREATED", "PASSWORD_CHANGED"} <= kinds
    assert "LOGIN_FAILED" not in kinds and "LOGIN" not in kinds         # failures are counted on the account, not written to the chain
    blob = " ".join(r["d"] for r in rows) + bad.text
    for secret in ("a very quiet passphrase", "another quiet passphrase", token, stored):
        assert secret not in blob


def test_the_operator_creates_an_account_even_when_signup_is_off(client, monkeypatch):
    monkeypatch.delenv("BK_ALLOW_SIGNUP")
    body = {"name": "Operator Made", "username": "made.by.op", "password": PW}
    assert client.post("/admin/accounts", json=body).status_code == 403                       # needs the admin token
    r = client.post("/admin/accounts", json=body, headers=HEADERS_ADMIN)
    assert r.status_code == 201 and r.json()["username"] == "made.by.op" and "session_token" not in r.json()
    assert client.post("/admin/accounts", json=body, headers=HEADERS_ADMIN).status_code == 409
    weak = client.post("/admin/accounts", json={**body, "username": "weak.one", "password": "short"}, headers=HEADERS_ADMIN)
    assert weak.status_code == 400 and code(weak) == "PASSWORD_WEAK"
    assert login(client, "made.by.op").status_code == 200


def test_responses_that_carry_a_credential_are_never_cacheable(client):
    r = signup(client, "no.cache")
    assert r.headers["cache-control"] == "no-store"
    assert login(client, "no.cache").headers["cache-control"] == "no-store"
    t = bearer(r.json()["session_token"])
    assert client.post("/agents", headers=t, json={"name": "cache bot"}).headers["cache-control"] == "no-store"
    assert client.post("/admin/principals", json={"name": "k", "kind": "agent"}, headers=HEADERS_ADMIN).headers["cache-control"] == "no-store"
