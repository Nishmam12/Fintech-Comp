"""Shared fixtures. Tests run against the real Supabase Postgres in the bk_test schema (never mocks)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from budget_kernel import kernel
from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool
from budget_kernel.db.migrate import migrate


@pytest.fixture(scope="session")
def settings():
    return Settings.load()


@pytest.fixture(scope="session")
def pool(settings):
    migrate(settings, settings.test_schema)
    p = make_pool(settings, settings.test_schema, max_size=10)
    with p.connection() as c:  # clean slate; TRUNCATE is not blocked by the row-level append-only triggers
        c.execute("TRUNCATE principals, mandates, grants, transactions, ledger_movements, audit_events,"
                  " budget_buckets, inference_calls, chain_heads, grant_strikes CASCADE")
    yield p
    p.close()


def future(days: float = 30) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def scope(**over) -> dict:
    base = {"categories": ["cloud", "ads"], "recipients": ["aws", "google"], "per_tx_limit": 50_000,
            "can_delegate": True}
    base.update(over)
    return base


def new_principal(pool, name: str, kind: str = "agent"):
    with pool.connection() as c:
        return c.execute("INSERT INTO principals(name, kind) VALUES (%s, %s) RETURNING id", (name, kind)).fetchone()["id"]


@dataclass
class World:
    pool: object
    owner: uuid.UUID
    alice: uuid.UUID
    bob: uuid.UUID
    mandate_id: uuid.UUID
    root: uuid.UUID
    svc: uuid.UUID  # settlement-service principal

    def check(self):
        """Assert I1-I3 hold. Call after every step."""
        assert kernel.check_invariants(self.pool, self.mandate_id) == []

    def grant(self, gid) -> dict:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM grants WHERE id = %s", (gid,)).fetchone()

    def tx(self, tid) -> dict:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM transactions WHERE id = %s", (tid,)).fetchone()

    def audit_kinds(self) -> list[str]:
        with self.pool.connection() as c:
            return [r["kind"] for r in c.execute(
                "SELECT kind FROM audit_events WHERE mandate_id = %s ORDER BY id", (self.mandate_id,))]

    def db_now(self):
        """The database clock (the kernel's only time source; the local clock may differ)."""
        with self.pool.connection() as c:
            return c.execute("SELECT now() AS t").fetchone()["t"]

    def delegate(self, parent, holder, amount, key=None, **kw):
        # Default expiry = the parent's own expiry, so a child is never wider than its parent.
        expires = kw.pop("expires_at", None) or self.grant(parent)["expires_at"]
        return kernel.delegate(
            self.pool, parent_grant_id=parent, actor=kw.pop("actor", None) or self.owner, holder_principal_id=holder,
            amount=amount, expires_at=expires, scope=kw.pop("scope", None) or scope(),
            idempotency_key=key or uuid.uuid4().hex)

    def authorize(self, grant, actor, amount, key=None, **kw):
        args = dict(currency="USD", recipient="aws", category="cloud")
        args.update(kw)
        return kernel.authorize(self.pool, grant_id=grant, actor=actor, amount=amount,
                                idempotency_key=key or uuid.uuid4().hex, **args)


@pytest.fixture()
def world(pool) -> World:
    owner, alice, bob = (new_principal(pool, n, "human" if n == "owner" else "agent") for n in ("owner", "alice", "bob"))
    m = kernel.create_mandate(pool, owner_principal_id=owner, currency="USD", total=100_000, protected_reserve=10_000,
                              expires_at=future(30), scope=scope(per_tx_limit=100_000))
    w = World(pool, owner, alice, bob, m["mandate_id"], m["root_grant_id"], new_principal(pool, "settler", "service"))
    kernel.bind_settler(pool, mandate_id=w.mandate_id, actor=owner, principal_id=w.svc)
    w.check()
    return w
