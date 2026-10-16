"""Migration 006 (ADR-0009): hash-chained history, suspension schema, key lifecycle columns.

The hash is recomputed here in Python from raw column values, independently of the SQL trigger. If the two
ever disagree the trigger and the (future) verifier would disagree too.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from budget_kernel import kernel
from budget_kernel.db.migrate import MIGRATIONS_DIR
from tests.conftest import new_principal

ZERO = "0" * 64
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _f(v) -> str:
    if v is None:
        s = ""
    elif isinstance(v, datetime):
        d = v.astimezone(timezone.utc) - EPOCH
        s = str((d.days * 86_400 + d.seconds) * 1_000_000 + d.microseconds)
    else:
        s = str(v)
    return f"{len(s)}:{s}"


def audit_canon(r: dict, detail_text: str) -> str:
    cols = [r["id"], r["chain_key"], r["seq"], r["mandate_id"], r["kind"], r["actor_principal_id"],
            r["subject_id"], r["created_at"]]
    return "A|" + "|".join(_f(c) for c in cols) + "|" + _f(detail_text)


def movement_canon(r: dict) -> str:
    cols = [r["id"], r["chain_key"], r["seq"], r["mandate_id"], r["kind"], r["amount"], r["from_grant_id"],
            r["from_bucket"], r["to_grant_id"], r["to_bucket"], r["transaction_id"], r["actor_principal_id"],
            r["created_at"]]
    return "M|" + "|".join(_f(c) for c in cols)


def row_hash(prev: str, canon: str) -> str:
    return hashlib.sha256(f"BK1|{prev}|{canon}".encode("utf-8")).hexdigest()


def audit_rows(pool, mandate_id):
    with pool.connection() as c:
        return c.execute("SELECT *, detail::text AS detail_text FROM audit_events WHERE mandate_id = %s ORDER BY seq",
                         (mandate_id,)).fetchall()


def test_every_audit_row_is_chained_and_matches_an_independent_hash(world):
    kernel.authorize(world.pool, grant_id=world.root, actor=world.owner, amount=100, currency="USD",
                     recipient="aws", category="cloud", idempotency_key="chain-1")
    with world.pool.connection() as c:
        c.execute("INSERT INTO audit_events(mandate_id, kind, detail) VALUES (%s, 'TEST|PIPE', %s)",
                  (world.mandate_id, Jsonb({"text": "a|b ünïcode", "n": [1, 2]})))
    rows = audit_rows(world.pool, world.mandate_id)
    assert len(rows) >= 3
    for r in rows:
        assert r["chain_key"] == f"mandate:{world.mandate_id}"
        assert len(r["row_hash"]) == 64 and len(r["prev_hash"]) == 64
    with world.pool.connection() as c:   # audit and ledger rows share one chain, so link across both tables
        both = c.execute(
            "SELECT seq, prev_hash, row_hash FROM audit_events WHERE mandate_id = %s UNION ALL"
            " SELECT seq, prev_hash, row_hash FROM ledger_movements WHERE mandate_id = %s ORDER BY seq",
            (world.mandate_id, world.mandate_id)).fetchall()
    assert both[0]["prev_hash"] == ZERO
    for prev, cur in zip(both, both[1:]):
        assert cur["prev_hash"] == prev["row_hash"]
    for r in rows:
        assert r["row_hash"] == row_hash(r["prev_hash"], audit_canon(r, r["detail_text"])), f"seq {r['seq']}"


def test_ledger_and_audit_share_one_gapless_sequence(world):
    world.authorize(world.root, world.owner, 500)
    with world.pool.connection() as c:
        seqs = sorted(r["seq"] for r in c.execute(
            "SELECT seq FROM audit_events WHERE mandate_id = %s UNION ALL"
            " SELECT seq FROM ledger_movements WHERE mandate_id = %s", (world.mandate_id, world.mandate_id)))
        head = c.execute("SELECT * FROM chain_heads WHERE chain_key = %s",
                         (f"mandate:{world.mandate_id}",)).fetchone()
    assert seqs == list(range(1, len(seqs) + 1))
    assert head["seq"] == len(seqs)


def test_ledger_movement_hash_matches_independent_recomputation(world):
    world.authorize(world.root, world.owner, 700)
    with world.pool.connection() as c:
        rows = c.execute("SELECT * FROM ledger_movements WHERE mandate_id = %s ORDER BY seq",
                         (world.mandate_id,)).fetchall()
    assert rows
    for r in rows:
        assert r["row_hash"] == row_hash(r["prev_hash"], movement_canon(r)), f"seq {r['seq']}"


def test_chain_head_is_the_last_row_hash(world):
    world.authorize(world.root, world.owner, 100)
    with world.pool.connection() as c:
        head = c.execute("SELECT * FROM chain_heads WHERE chain_key = %s",
                         (f"mandate:{world.mandate_id}",)).fetchone()
        last = c.execute(
            "SELECT row_hash, seq FROM (SELECT row_hash, seq FROM audit_events WHERE mandate_id = %s UNION ALL"
            " SELECT row_hash, seq FROM ledger_movements WHERE mandate_id = %s) x ORDER BY seq DESC LIMIT 1",
            (world.mandate_id, world.mandate_id)).fetchone()
    assert head["head_hash"] == last["row_hash"] and head["seq"] == last["seq"]


def test_application_cannot_choose_chain_values(world):
    with world.pool.connection() as c:
        r = c.execute(
            "INSERT INTO audit_events(mandate_id, kind, chain_key, seq, prev_hash, row_hash)"
            " VALUES (%s, 'FORGED', 'mandate:fake', 999, %s, %s) RETURNING *",
            (world.mandate_id, "f" * 64, "e" * 64)).fetchone()
    assert r["chain_key"] == f"mandate:{world.mandate_id}"
    assert r["seq"] != 999 and r["prev_hash"] != "f" * 64 and r["row_hash"] != "e" * 64


def test_global_chain_for_rows_without_a_mandate(pool):
    with pool.connection() as c:
        a = c.execute("INSERT INTO audit_events(kind) VALUES ('GLOBAL_A') RETURNING *").fetchone()
        b = c.execute("INSERT INTO audit_events(kind) VALUES ('GLOBAL_B') RETURNING *").fetchone()
    assert a["chain_key"] == b["chain_key"] == "global"
    assert b["seq"] == a["seq"] + 1 and b["prev_hash"] == a["row_hash"]


def test_a_rolled_back_write_leaves_no_gap(world):
    key = f"mandate:{world.mandate_id}"
    with world.pool.connection() as c:
        before = c.execute("SELECT seq, head_hash FROM chain_heads WHERE chain_key = %s", (key,)).fetchone()
        with pytest.raises(RuntimeError):
            with c.transaction():
                c.execute("INSERT INTO audit_events(mandate_id, kind) VALUES (%s, 'ROLLED_BACK')", (world.mandate_id,))
                raise RuntimeError("abort")
        after = c.execute("SELECT seq, head_hash FROM chain_heads WHERE chain_key = %s", (key,)).fetchone()
    assert before == after


@pytest.mark.parametrize("table", ["audit_events", "ledger_movements"])
def test_chained_history_is_still_append_only(world, table):
    world.authorize(world.root, world.owner, 100)
    with world.pool.connection() as c:
        with pytest.raises(psycopg.errors.RaiseException):
            with c.transaction():
                c.execute(sql.SQL("UPDATE {} SET kind = 'x' WHERE mandate_id = %s").format(sql.Identifier(table)),
                          (world.mandate_id,))


# ---------------------------------------------------------------- suspension schema

def test_grant_status_accepts_suspended_only_with_its_columns(world):
    with world.pool.connection() as c:
        with pytest.raises(psycopg.errors.CheckViolation):          # suspended but no suspended_at
            with c.transaction():
                c.execute("UPDATE grants SET status = 'suspended' WHERE id = %s", (world.root,))
        with pytest.raises(psycopg.errors.CheckViolation):          # suspended_at set but status active
            with c.transaction():
                c.execute("UPDATE grants SET suspended_at = now(), suspend_reason = 'MANUAL' WHERE id = %s",
                          (world.root,))
        with pytest.raises(psycopg.errors.CheckViolation):          # unknown reason
            with c.transaction():
                c.execute("UPDATE grants SET status = 'suspended', suspended_at = now(), suspend_reason = 'BAD'"
                          " WHERE id = %s", (world.root,))
        c.execute("UPDATE grants SET status = 'suspended', suspended_at = now(), suspend_reason = 'STRIKES'"
                  " WHERE id = %s", (world.root,))
        c.execute("UPDATE grants SET status = 'active', suspended_at = NULL, suspend_reason = NULL,"
                  " reinstated_at = now() WHERE id = %s", (world.root,))


def test_grant_strikes_are_append_only_and_validated(world):
    with world.pool.connection() as c:
        c.execute("INSERT INTO grant_strikes(mandate_id, grant_id, actor_principal_id, kind, reason, weight)"
                  " VALUES (%s, %s, %s, 'REFUSAL', 'CATEGORY_NOT_ALLOWED', 1)",
                  (world.mandate_id, world.root, world.owner))
        with pytest.raises(psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO grant_strikes(mandate_id, grant_id, actor_principal_id, kind, reason, weight)"
                          " VALUES (%s, %s, %s, 'OTHER', 'x', 1)", (world.mandate_id, world.root, world.owner))
        with pytest.raises(psycopg.errors.RaiseException):
            with c.transaction():
                c.execute("UPDATE grant_strikes SET weight = 2 WHERE grant_id = %s", (world.root,))
        with pytest.raises(psycopg.errors.RaiseException):
            with c.transaction():
                c.execute("DELETE FROM grant_strikes WHERE grant_id = %s", (world.root,))


# ---------------------------------------------------------------- key lifecycle and budget bucket

def test_principals_have_key_lifecycle_columns(pool):
    pid = new_principal(pool, "lifecycle")
    with pool.connection() as c:
        r = c.execute("SELECT key_expires_at, disabled_at, key_rotated_at FROM principals WHERE id = %s",
                      (pid,)).fetchone()
    assert r == {"key_expires_at": None, "disabled_at": None, "key_rotated_at": None}


def test_per_agent_budget_bucket_names_are_accepted(pool):
    month = datetime.now(timezone.utc).date().replace(day=1)
    ok = f"principal:{uuid.uuid4()}"
    with pool.connection() as c:
        c.execute("INSERT INTO budget_buckets(month, bucket, cap_micro_usd) VALUES (%s, %s, 500000)", (month, ok))
        for bad in ("principal:not-a-uuid", "principal:", "other"):
            with pytest.raises(psycopg.errors.CheckViolation):
                with c.transaction():
                    c.execute("INSERT INTO budget_buckets(month, bucket, cap_micro_usd) VALUES (%s, %s, 1)",
                              (month, bad))
        c.execute("DELETE FROM budget_buckets WHERE bucket = %s", (ok,))


def test_row_level_security_is_on_for_new_tables(pool):
    with pool.connection() as c:
        rows = c.execute(
            "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('chain_heads', 'grant_strikes')"
            " AND relnamespace = current_schema()::regnamespace").fetchall()
    assert {r["relname"]: r["relrowsecurity"] for r in rows} == {"chain_heads": True, "grant_strikes": True}


# ---------------------------------------------------------------- backfill on a populated schema

def _run_file(conn, name):
    conn.execute((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))


def test_migration_006_backfills_existing_history_into_a_valid_chain(settings):
    schema = f"{settings.test_schema}_bf"
    with psycopg.connect(settings.database_url, connect_timeout=15, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        c.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for name in sorted(p.name for p in MIGRATIONS_DIR.glob("00[1-5]_*.sql")):
            _run_file(c, name)
        owner = c.execute("INSERT INTO principals(name, kind) VALUES ('o', 'human') RETURNING id").fetchone()[0]
        mid = c.execute(
            "INSERT INTO mandates(owner_principal_id, currency, total, protected_reserve, expires_at)"
            " VALUES (%s, 'USD', 1000, 0, now() + interval '1 day') RETURNING id", (owner,)).fetchone()[0]
        for i in range(3):
            c.execute("INSERT INTO audit_events(mandate_id, kind, detail) VALUES (%s, %s, %s)",
                      (mid, f"OLD_{i}", Jsonb({"i": i})))
        c.execute("INSERT INTO audit_events(kind) VALUES ('OLD_GLOBAL')")
        c.execute("INSERT INTO ledger_movements(mandate_id, kind, amount, to_bucket) VALUES (%s, 'fund', 1000, 'x')",
                  (mid,))
        _run_file(c, "006_robustness_ii.sql")
        rows = c.execute(
            "SELECT 'A' t, id, chain_key, seq, prev_hash, row_hash FROM audit_events WHERE mandate_id = %s UNION ALL"
            " SELECT 'M', id, chain_key, seq, prev_hash, row_hash FROM ledger_movements WHERE mandate_id = %s"
            " ORDER BY 4", (mid, mid)).fetchall()
        head = c.execute("SELECT seq, head_hash FROM chain_heads WHERE chain_key = %s", (f"mandate:{mid}",)).fetchone()
        glob = c.execute("SELECT count(*) FROM audit_events WHERE chain_key = 'global'").fetchone()[0]
        c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    assert [r[3] for r in rows] == [1, 2, 3, 4]
    assert rows[0][4] == ZERO
    assert all(b[4] == a[5] for a, b in zip(rows, rows[1:]))
    assert head == (4, rows[-1][5])
    assert glob == 1


# ---------------------------------------------------------------- kernel stubs (signatures frozen by ADR-0009 B5)

def test_phase3_kernel_api_is_exported_with_frozen_signatures():
    import inspect

    expect = {
        "record_signal": ["pool", "grant_id", "actor", "kind", "reason"],
        "suspend": ["pool", "grant_id", "actor"],
        "reinstate": ["pool", "grant_id", "actor"],
        "tick": ["pool", "mandate_id"],
        "due_mandates": ["pool", "limit"],
    }
    for name, params in expect.items():
        fn = getattr(kernel, name)
        assert list(inspect.signature(fn).parameters) == params, name


def test_unimplemented_breaker_operations_fail_closed(world):
    with pytest.raises(NotImplementedError):
        kernel.suspend(world.pool, grant_id=world.root, actor=world.owner)
    with pytest.raises(NotImplementedError):
        kernel.reinstate(world.pool, grant_id=world.root, actor=world.owner)
    with pytest.raises(NotImplementedError):
        kernel.record_signal(world.pool, grant_id=world.root, actor=world.owner, kind="INJECTION", reason="x")


def test_tick_runs_the_sweep_and_reports_what_it_did(world):
    r = kernel.tick(world.pool, world.mandate_id)
    assert r == {"mandate_id": str(world.mandate_id), "expired_grants": 0, "released": 0, "review_expired": 0}


def test_tick_releases_an_expired_reservation(world):
    tx = world.authorize(world.root, world.owner, 300)
    with world.pool.connection() as c:
        c.execute("UPDATE transactions SET reserve_expires_at = now() - interval '1 minute' WHERE id = %s",
                  (tx["transaction_id"],))
    assert kernel.due_mandates(world.pool, limit=500).count(world.mandate_id) == 1
    r = kernel.tick(world.pool, world.mandate_id)
    assert r["released"] == 1
    assert world.tx(tx["transaction_id"])["state"] == "released"
    world.check()
    assert world.mandate_id not in kernel.due_mandates(world.pool, limit=500)


def test_due_mandates_ignores_quiet_mandates(world):
    assert world.mandate_id not in kernel.due_mandates(world.pool, limit=500)
