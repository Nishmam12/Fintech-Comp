"""ADR-0009 part A4: the hash-chain verifier and GET /mandates/{id}/integrity.

Tampering is done the way an operator with table-owner rights would do it: the append-only trigger is lifted
inside one transaction, rows are edited, the trigger is restored. The anchor tests run in a scratch schema
(migrations 001-006 plus the two anchor tables exactly as ADR-0009 A5 freezes them), so they do not depend on
Afnan's migration 007.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from budget_kernel import kernel
from budget_kernel.api.app import create_app
from budget_kernel.db.connection import make_pool
from budget_kernel.db.migrate import MIGRATIONS_DIR
from budget_kernel.kernel import integrity
from tests.conftest import World, future, new_principal, scope

ZERO = "0" * 64
ANCHOR_TABLES = """
CREATE TABLE anchors (
  id bigserial PRIMARY KEY, chain_id int NOT NULL, from_address text NOT NULL, nonce bigint NOT NULL,
  digest text NOT NULL, raw_tx bytea NOT NULL, tx_hash text NOT NULL UNIQUE,
  status text NOT NULL CHECK (status IN ('signed','broadcast','confirmed','failed','stuck')),
  broadcast_attempts int NOT NULL DEFAULT 0, last_error text, block_number bigint,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE anchor_heads (
  anchor_id bigint NOT NULL REFERENCES anchors(id), chain_key text NOT NULL, seq bigint NOT NULL,
  head_hash text NOT NULL, PRIMARY KEY (anchor_id, chain_key));
"""


@contextmanager
def tamper(conn):
    """One transaction: lift the append-only triggers, let the caller edit, restore them, commit."""
    with conn.transaction():
        for t in ("audit_events", "ledger_movements"):
            conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(
                sql.Identifier(t), sql.Identifier(f"{t}_append_only")))
        yield
        for t in ("audit_events", "ledger_movements"):
            conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER {}").format(
                sql.Identifier(t), sql.Identifier(f"{t}_append_only")))


def chain_rows(conn, mandate_id):
    return conn.execute(
        "SELECT 'audit_events' AS t, id, seq FROM audit_events WHERE mandate_id = %s UNION ALL"
        " SELECT 'ledger_movements', id, seq FROM ledger_movements WHERE mandate_id = %s ORDER BY seq",
        (mandate_id, mandate_id)).fetchall()


def rewrite_chain(conn, mandate_id):
    """What a database superuser could do: recompute every hash so the chain is self-consistent again."""
    prev = ZERO
    for r in chain_rows(conn, mandate_id):
        prev = conn.execute(
            sql.SQL("UPDATE {t} a SET prev_hash = %s, row_hash = bk_hash(%s, bk_canon(%s, a)) WHERE id = %s"
                    " RETURNING row_hash").format(t=sql.Identifier(r["t"])),
            (prev, prev, r["t"], r["id"])).fetchone()["row_hash"]
    conn.execute("UPDATE chain_heads SET head_hash = %s WHERE chain_key = %s", (prev, f"mandate:{mandate_id}"))


def busy_world(world: World):
    world.authorize(world.root, world.owner, 400)
    world.authorize(world.root, world.owner, 600)
    return world


# ---------------------------------------------------------------- verifier

def test_an_untouched_chain_verifies(world):
    busy_world(world)
    r = integrity.verify(world.pool, world.mandate_id)
    assert r["ok"] is True and r["broken_at"] is None and r["reason"] is None
    assert r["chain_key"] == f"mandate:{world.mandate_id}"
    assert r["length"] == r["head_seq"] >= 6
    with world.pool.connection() as c:
        head = c.execute("SELECT head_hash FROM chain_heads WHERE chain_key = %s", (r["chain_key"],)).fetchone()
    assert r["head_hash"] == head["head_hash"]
    assert r["last_anchor"] is None and r["verified_at"]


def test_unknown_mandate_is_not_found(pool):
    with pytest.raises(kernel.NotFound):
        integrity.verify(pool, uuid.uuid4())


def test_edited_audit_detail_is_detected_at_that_row(world):
    busy_world(world)
    with world.pool.connection() as c:
        row = c.execute("SELECT id, seq FROM audit_events WHERE mandate_id = %s AND kind = 'TX_RESERVED'"
                        " ORDER BY seq LIMIT 1", (world.mandate_id,)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET detail = '{\"amount\": 1}'::jsonb WHERE id = %s", (row["id"],))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"], r["broken_at"]) == (False, "HASH_MISMATCH", row["seq"])


def test_edited_ledger_amount_is_detected(world):
    busy_world(world)
    with world.pool.connection() as c:
        row = c.execute("SELECT id, seq FROM ledger_movements WHERE mandate_id = %s AND kind = 'reserve'"
                        " ORDER BY seq LIMIT 1", (world.mandate_id,)).fetchone()
        with tamper(c):
            c.execute("UPDATE ledger_movements SET amount = amount + 1 WHERE id = %s", (row["id"],))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"], r["broken_at"]) == (False, "HASH_MISMATCH", row["seq"])


def test_a_deleted_row_in_the_middle_is_a_sequence_gap(world):
    busy_world(world)
    with world.pool.connection() as c:
        row = c.execute("SELECT id, seq FROM audit_events WHERE mandate_id = %s ORDER BY seq OFFSET 2 LIMIT 1",
                        (world.mandate_id,)).fetchone()
        with tamper(c):
            c.execute("DELETE FROM audit_events WHERE id = %s", (row["id"],))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"], r["broken_at"]) == (False, "SEQ_GAP", row["seq"])


def test_an_edit_with_a_recomputed_hash_breaks_the_next_link(world):
    busy_world(world)
    with world.pool.connection() as c:
        row = c.execute("SELECT id, seq FROM audit_events WHERE mandate_id = %s AND kind = 'TX_RESERVED'"
                        " ORDER BY seq LIMIT 1", (world.mandate_id,)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET detail = '{\"amount\": 1}'::jsonb WHERE id = %s", (row["id"],))
            c.execute("UPDATE audit_events a SET row_hash = bk_hash(a.prev_hash, bk_canon('audit_events', a))"
                      " WHERE id = %s", (row["id"],))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"], r["broken_at"]) == (False, "PREV_MISMATCH", row["seq"] + 1)


def test_deleting_the_newest_row_is_caught_by_the_head(world):
    busy_world(world)
    with world.pool.connection() as c:
        last = chain_rows(c, world.mandate_id)[-1]
        with tamper(c):
            c.execute(sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(last["t"])), (last["id"],))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"]) == (False, "HEAD_MISMATCH")


def test_a_forged_chain_head_is_detected(world):
    busy_world(world)
    with world.pool.connection() as c:
        c.execute("UPDATE chain_heads SET head_hash = %s WHERE chain_key = %s",
                  ("a" * 64, f"mandate:{world.mandate_id}"))
    r = integrity.verify(world.pool, world.mandate_id)
    assert (r["ok"], r["reason"]) == (False, "HEAD_MISMATCH")


def test_a_full_consistent_rewrite_without_an_anchor_is_not_detected(world):
    """The honest limit (ADR-0009 A6): without an anchor, a superuser can rewrite a whole chain consistently."""
    busy_world(world)
    with world.pool.connection() as c:
        row = c.execute("SELECT id FROM audit_events WHERE mandate_id = %s AND kind = 'TX_RESERVED' LIMIT 1",
                        (world.mandate_id,)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET detail = '{\"amount\": 1}'::jsonb WHERE id = %s", (row["id"],))
            rewrite_chain(c, world.mandate_id)
    assert integrity.verify(world.pool, world.mandate_id)["ok"] is True


def test_verification_is_read_only_and_takes_no_mandate_lock(world):
    busy_world(world)
    with world.pool.connection() as holder:
        with holder.transaction():
            holder.execute("SELECT 1 FROM mandates WHERE id = %s FOR UPDATE", (world.mandate_id,))
            assert integrity.verify(world.pool, world.mandate_id)["ok"] is True   # would time out if it locked


# ---------------------------------------------------------------- anchors (scratch schema)

@pytest.fixture()
def scratch(settings):
    schema = f"{settings.test_schema}_an"
    with psycopg.connect(settings.database_url, connect_timeout=15, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        c.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for p in sorted(MIGRATIONS_DIR.glob("00[1-6]_*.sql")):
            c.execute(p.read_text(encoding="utf-8"))
        c.execute(ANCHOR_TABLES)
    pool = make_pool(settings, schema, max_size=4)
    owner, agent = (new_principal(pool, n, "human" if n == "o" else "agent") for n in ("o", "a"))
    m = kernel.create_mandate(pool, owner_principal_id=owner, currency="USD", total=100_000, protected_reserve=0,
                              expires_at=future(30), scope=scope(per_tx_limit=100_000))
    for amount in (400, 600):
        kernel.authorize(pool, grant_id=m["root_grant_id"], actor=owner, amount=amount, currency="USD",
                         recipient="aws", category="cloud", idempotency_key=uuid.uuid4().hex)
    yield pool, m["mandate_id"], m["root_grant_id"], owner
    pool.close()
    with psycopg.connect(settings.database_url, connect_timeout=15, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


def anchor_now(pool, mandate_id, status="confirmed"):
    with pool.connection() as c:
        h = c.execute("SELECT seq, head_hash FROM chain_heads WHERE chain_key = %s", (f"mandate:{mandate_id}",)).fetchone()
        aid = c.execute(
            "INSERT INTO anchors(chain_id, from_address, nonce, digest, raw_tx, tx_hash, status)"
            " VALUES (84532, '0xabc', %s, %s, '\\x00', %s, %s) RETURNING id",
            (uuid.uuid4().int % 10**9, "d" * 64, "0x" + uuid.uuid4().hex * 2, status)).fetchone()["id"]
        c.execute("INSERT INTO anchor_heads VALUES (%s, %s, %s, %s)", (aid, f"mandate:{mandate_id}", h["seq"], h["head_hash"]))
    return aid, h


def test_a_matching_confirmed_anchor_is_reported(scratch):
    pool, mid, *_ = scratch
    aid, h = anchor_now(pool, mid)
    r = integrity.verify(pool, mid)
    assert r["ok"] is True
    la = r["last_anchor"]
    assert (la["anchor_id"], la["seq"], la["head_hash"], la["status"], la["matches"]) == (aid, h["seq"], h["head_hash"], "confirmed", True)
    assert la["tx_hash"].startswith("0x")


def test_history_can_grow_after_an_anchor(scratch):
    pool, mid, root, owner = scratch
    anchor_now(pool, mid)
    kernel.authorize(pool, grant_id=root, actor=owner, amount=100, currency="USD", recipient="aws",
                     category="cloud", idempotency_key=uuid.uuid4().hex)
    r = integrity.verify(pool, mid)
    assert r["ok"] is True and r["last_anchor"]["matches"] is True


def test_a_full_rewrite_after_an_anchor_is_caught(scratch):
    pool, mid, *_ = scratch
    anchor_now(pool, mid)
    with pool.connection() as c:
        row = c.execute("SELECT id FROM audit_events WHERE mandate_id = %s AND kind = 'TX_RESERVED' LIMIT 1", (mid,)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET detail = '{\"amount\": 1}'::jsonb WHERE id = %s", (row["id"],))
            rewrite_chain(c, mid)
    r = integrity.verify(pool, mid)
    assert (r["ok"], r["reason"]) == (False, "ANCHOR_MISMATCH")
    assert r["last_anchor"]["matches"] is False


def test_an_unconfirmed_anchor_is_shown_but_not_enforced(scratch):
    pool, mid, *_ = scratch
    anchor_now(pool, mid, status="broadcast")
    with pool.connection() as c:
        row = c.execute("SELECT id FROM audit_events WHERE mandate_id = %s AND kind = 'TX_RESERVED' LIMIT 1", (mid,)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET detail = '{\"amount\": 1}'::jsonb WHERE id = %s", (row["id"],))
            rewrite_chain(c, mid)
    r = integrity.verify(pool, mid)
    assert r["ok"] is True and r["last_anchor"]["status"] == "broadcast" and r["last_anchor"]["matches"] is False


def test_rows_removed_after_an_anchor_are_caught(scratch):
    pool, mid, *_ = scratch
    anchor_now(pool, mid)
    with pool.connection() as c:
        last = chain_rows(c, mid)[-1]
        with tamper(c):
            c.execute(sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(last["t"])), (last["id"],))
            c.execute("UPDATE chain_heads SET seq = seq - 1, head_hash = (SELECT row_hash FROM ("
                      " SELECT row_hash, seq FROM audit_events WHERE mandate_id = %s UNION ALL"
                      " SELECT row_hash, seq FROM ledger_movements WHERE mandate_id = %s) x ORDER BY seq DESC LIMIT 1)"
                      " WHERE chain_key = %s", (mid, mid, f"mandate:{mid}"))
    r = integrity.verify(pool, mid)
    assert (r["ok"], r["reason"]) == (False, "ANCHOR_MISMATCH")


# ---------------------------------------------------------------- HTTP

@pytest.fixture()
def api(pool, monkeypatch):
    monkeypatch.setenv("BK_ADMIN_TOKEN", "t")
    with TestClient(create_app(pool=pool)) as client:
        yield client


def _person(client, kind):
    r = client.post("/admin/principals", json={"name": f"ig-{uuid.uuid4().hex[:6]}", "kind": kind},
                    headers={"X-Admin-Token": "t"}).json()
    return r["principal_id"], {"Authorization": f"Bearer {r['api_key']}"}


def test_integrity_endpoint_for_owner_and_admin_only(api):
    _, owner = _person(api, "human")
    agent_id, agent = _person(api, "agent")
    exp = future(10).isoformat()
    sc = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": True}
    m = api.post("/mandates", headers=owner, json={"currency": "USD", "total": 100_000, "protected_reserve": 0,
                                                   "expires_at": exp, "scope": sc}).json()
    api.post("/grants", headers=owner, json={"parent_grant_id": m["root_grant_id"], "holder_principal_id": agent_id,
                                             "amount": 1_000, "expires_at": exp, "idempotency_key": uuid.uuid4().hex,
                                             "scope": {**sc, "can_delegate": False}})
    url = f"/mandates/{m['mandate_id']}/integrity"

    r = api.get(url, headers=owner)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["mandate_id"] == m["mandate_id"] and body["last_anchor"] is None
    assert set(body) == {"mandate_id", "chain_key", "ok", "length", "head_seq", "head_hash", "broken_at", "reason",
                         "verified_at", "last_anchor"}
    assert api.get(url, headers={"X-Admin-Token": "t"}).status_code == 200
    holder = api.get(url, headers=agent)
    assert holder.status_code == 403 and holder.json()["code"] == "NOT_OWNER"
    assert api.get(url).status_code == 401
    assert api.get(url, headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert api.get(f"/mandates/{uuid.uuid4()}/integrity", headers=owner).status_code == 404
    assert api.get("/mandates/not-a-uuid/integrity", headers=owner).status_code == 422


def test_integrity_endpoint_reports_tampering(api, pool):
    _, owner = _person(api, "human")
    exp = future(10).isoformat()
    sc = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 20_000, "can_delegate": True}
    m = api.post("/mandates", headers=owner, json={"currency": "USD", "total": 100_000, "protected_reserve": 0,
                                                   "expires_at": exp, "scope": sc}).json()
    with pool.connection() as c:
        row = c.execute("SELECT id, seq FROM audit_events WHERE mandate_id = %s ORDER BY seq LIMIT 1",
                        (m["mandate_id"],)).fetchone()
        with tamper(c):
            c.execute("UPDATE audit_events SET kind = 'EDITED' WHERE id = %s", (row["id"],))
    body = api.get(f"/mandates/{m['mandate_id']}/integrity", headers=owner).json()
    assert (body["ok"], body["reason"], body["broken_at"]) == (False, "HASH_MISMATCH", row["seq"])
