"""Username and password login, sessions, sign-up and password change (docs/plans/LOGIN_PLAN.md).

Principle: this changes who can obtain a credential, not what a credential can do. A session token resolves to the same
Principal as an API key (auth.current_principal), so no kernel, ledger or permission code is involved.

Failures: one generic error (INVALID_CREDENTIALS) for a wrong password, an unknown username, a locked account and a
disabled one, and an unknown username costs the same time as a wrong password (a fixed dummy hash is verified). Failed
attempts are counted on the account and are NOT written to the hash-chained audit, so a flood of guesses cannot flood the
chain (R14). Nothing secret is logged or audited: only account creation and password changes leave an audit row."""
from __future__ import annotations

import os
import re

from fastapi import FastAPI, Header, HTTPException, Request
from psycopg.errors import UniqueViolation

from budget_kernel.kernel.tx import audit

from . import schemas
from .auth import SESSION_PREFIX, Caller, Principal, hash_key, new_key, new_session_token
from .passwords import DUMMY_HASH, hash_password, policy_problem, verify_password

LOCK_AFTER = 5                 # consecutive wrong passwords before the account locks
LOCK_MINUTES = 15
MAX_AGENTS = 10                # agent principals one person may create (setup flow); more is an operator task
MAX_SESSIONS = 20              # live sessions kept per person; the oldest beyond this are removed at the next login
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

INVALID = {"code": "INVALID_CREDENTIALS", "message": "wrong username or password"}


def _session_hours() -> int:
    try:
        return max(1, min(168, int(os.environ.get("BK_SESSION_HOURS", "12"))))
    except ValueError:
        return 12


def _issue_session(c, principal_id):
    token = new_session_token()
    row = c.execute("INSERT INTO sessions(token_hash, principal_id, expires_at)"
                    " VALUES (%s, %s, clock_timestamp() + make_interval(hours => %s)) RETURNING expires_at",
                    (hash_key(token), principal_id, _session_hours())).fetchone()
    c.execute("DELETE FROM sessions WHERE principal_id = %s AND expires_at < clock_timestamp() - interval '1 day'", (principal_id,))
    c.execute("DELETE FROM sessions WHERE principal_id = %s AND token_hash NOT IN"
              " (SELECT token_hash FROM sessions WHERE principal_id = %s ORDER BY created_at DESC LIMIT %s)",
              (principal_id, principal_id, MAX_SESSIONS))
    return token, row["expires_at"]


def _register_failure(c, principal_id) -> None:
    """Count one wrong password; the fifth in a row locks the account (the clock is the database's)."""
    c.execute("UPDATE principals SET failed_logins = failed_logins + 1,"
              " locked_until = CASE WHEN failed_logins + 1 >= %s THEN clock_timestamp() + make_interval(mins => %s) ELSE locked_until END"
              " WHERE id = %s", (LOCK_AFTER, LOCK_MINUTES, principal_id))


def _presented(authorization: str) -> str:
    return authorization.partition(" ")[2]


def _signup_allowed() -> bool:
    return os.environ.get("BK_ALLOW_SIGNUP") == "1"


def _normalise_username(raw: str) -> str:
    u = raw.strip().lower()
    if not USERNAME.match(u):
        raise HTTPException(400, {"code": "USERNAME_INVALID",
                                  "message": "Use 3 to 32 letters, digits, dots, dashes or underscores, starting with a letter or digit."})
    return u


def install(app: FastAPI, P) -> None:
    def session_body(token, expires_at, pid, name, kind, username):
        return {"session_token": token, "expires_at": expires_at.isoformat(),
                "principal": {"principal_id": str(pid), "name": name, "kind": kind, "username": username}}

    @app.get("/auth/config")
    def auth_config():
        """Tells the sign-in screen whether it should offer 'Create account'."""
        return {"signup": _signup_allowed()}

    @app.post("/auth/signup", status_code=201)
    def signup(body: schemas.Signup, request: Request):
        if not _signup_allowed():
            raise HTTPException(403, {"code": "SIGNUP_DISABLED", "message": "accounts are created by the operator on this server"})
        username = _normalise_username(body.username)
        problem = policy_problem(body.password, username)
        if problem:
            raise HTTPException(400, {"code": "PASSWORD_WEAK", "message": problem})
        name = body.name.strip()
        if not name:
            raise HTTPException(400, {"code": "NAME_REQUIRED", "message": "Enter your name."})
        pwhash = hash_password(body.password)                    # the slow part, outside the transaction
        taken = False
        try:
            with P(request).connection() as c:
                row = c.execute("INSERT INTO principals(name, kind, username, password_hash, password_changed_at)"
                                " VALUES (%s, 'human', %s, %s, clock_timestamp()) RETURNING id",
                                (name, username, pwhash)).fetchone()
                audit(c, None, "ACCOUNT_CREATED", row["id"], row["id"])
                token, exp = _issue_session(c, row["id"])
        except UniqueViolation:
            taken = True
        if taken:
            raise HTTPException(409, {"code": "USERNAME_TAKEN", "message": "that username is taken"})
        return session_body(token, exp, row["id"], name, "human", username)

    @app.post("/auth/login")
    def login(body: schemas.Login, request: Request):
        username = body.username.strip().lower()
        result = None
        with P(request).connection() as c:
            row = c.execute("SELECT id, name, kind, username, password_hash, disabled_at,"
                            " coalesce(locked_until > clock_timestamp(), false) AS locked"
                            " FROM principals WHERE username = %s FOR UPDATE", (username,)).fetchone()
            has_password = row is not None and row["password_hash"] is not None
            ok = verify_password(body.password, row["password_hash"] if has_password else DUMMY_HASH)
            if has_password and not row["locked"]:
                if ok and row["disabled_at"] is None:
                    c.execute("UPDATE principals SET failed_logins = 0, locked_until = NULL WHERE id = %s", (row["id"],))
                    token, exp = _issue_session(c, row["id"])
                    result = session_body(token, exp, row["id"], row["name"], row["kind"], row["username"])
                elif not ok:
                    _register_failure(c, row["id"])
        if result is None:                                       # raised after the block so the failure count is committed
            raise HTTPException(401, INVALID)
        return result

    @app.post("/auth/logout")
    def logout(request: Request, authorization: str = Header(default=""), me: Principal = Caller):
        raw = _presented(authorization)
        if not raw.startswith(SESSION_PREFIX):
            raise HTTPException(400, {"code": "NOT_A_SESSION", "message": "an API key has no session to end"})
        with P(request).connection() as c:
            c.execute("UPDATE sessions SET revoked_at = clock_timestamp() WHERE token_hash = %s AND revoked_at IS NULL", (hash_key(raw),))
        return {"ok": True}

    @app.post("/me/password")
    def change_password(body: schemas.ChangePassword, request: Request, authorization: str = Header(default=""),
                        me: Principal = Caller):
        problem = policy_problem(body.new_password)
        if problem:
            raise HTTPException(400, {"code": "PASSWORD_WEAK", "message": problem})
        new_hash = hash_password(body.new_password)
        outcome = "ok"
        with P(request).connection() as c:
            row = c.execute("SELECT username, password_hash, coalesce(locked_until > clock_timestamp(), false) AS locked"
                            " FROM principals WHERE id = %s FOR UPDATE", (me.id,)).fetchone()
            if row is None or row["password_hash"] is None:
                outcome = "none"
            else:
                ok = verify_password(body.current_password, row["password_hash"])
                if row["locked"] or not ok:
                    outcome = "bad"
                    if not row["locked"]:
                        _register_failure(c, me.id)
                elif policy_problem(body.new_password, row["username"]):
                    outcome = "weak"
                else:
                    c.execute("UPDATE principals SET password_hash = %s, password_changed_at = clock_timestamp(),"
                              " failed_logins = 0, locked_until = NULL WHERE id = %s", (new_hash, me.id))
                    c.execute("UPDATE sessions SET revoked_at = clock_timestamp()"
                              " WHERE principal_id = %s AND revoked_at IS NULL AND token_hash <> %s",
                              (me.id, hash_key(_presented(authorization))))
                    audit(c, None, "PASSWORD_CHANGED", me.id, me.id)
        if outcome == "none":
            raise HTTPException(400, {"code": "NO_PASSWORD_SET", "message": "this account signs in with an API key"})
        if outcome == "bad":
            raise HTTPException(401, INVALID)
        if outcome == "weak":
            raise HTTPException(400, {"code": "PASSWORD_WEAK", "message": "That password is too easy to guess. Pick something else."})
        return {"ok": True}

    # ------------------------------------------------------------------ setup flow: agents

    def require_human(me: Principal) -> None:
        if me.kind != "human":
            raise HTTPException(403, {"code": "HUMAN_ONLY", "message": "only a person can create or list agents"})

    @app.post("/agents", status_code=201)
    def create_agent(body: schemas.CreateAgent, request: Request, me: Principal = Caller):
        """A person creates an agent principal and gets its API key once. The agent has no authority until a grant gives it some;
        it never gets a password or a session."""
        require_human(me)
        raw = new_key()
        full = False
        with P(request).connection() as c:
            c.execute("SELECT 1 FROM principals WHERE id = %s FOR UPDATE", (me.id,))      # serialises this person's creations
            n = c.execute("SELECT count(*) AS n FROM principals WHERE created_by = %s", (me.id,)).fetchone()["n"]
            if n >= MAX_AGENTS:
                full = True
            else:
                row = c.execute("INSERT INTO principals(name, kind, api_key_hash, created_by) VALUES (%s, 'agent', %s, %s)"
                                " RETURNING id", (body.name, hash_key(raw), me.id)).fetchone()
                audit(c, None, "AGENT_CREATED", me.id, row["id"])
        if full:
            raise HTTPException(409, {"code": "AGENT_LIMIT", "message": f"you can create up to {MAX_AGENTS} agents here"})
        return {"principal_id": str(row["id"]), "name": body.name, "api_key": raw,
                "note": "store this key now; it is not shown again"}

    @app.get("/agents")
    def list_agents(request: Request, me: Principal = Caller):
        require_human(me)
        with P(request).connection() as c:
            rows = c.execute("SELECT id, name, created_at FROM principals WHERE created_by = %s ORDER BY created_at", (me.id,)).fetchall()
        return {"agents": [{"principal_id": str(r["id"]), "name": r["name"], "created_at": r["created_at"].isoformat()} for r in rows]}
