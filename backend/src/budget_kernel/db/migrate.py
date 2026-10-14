"""Minimal forward-only migration runner: applies backend/migrations/*.sql in name order.

    python -m budget_kernel.db.migrate [--test]

Each file runs in one transaction and is recorded in <schema>.schema_migrations.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import psycopg
from psycopg import sql

from budget_kernel.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def migrate(settings: Settings, schema: str) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if f.name in done:
                continue
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations(name) VALUES (%s)", (f.name,))
            applied_now.append(f.name)
    return applied_now


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="migrate the test schema instead")
    args = ap.parse_args()
    st = Settings.load()
    target = st.test_schema if args.test else st.schema
    print(f"schema={target} applied={migrate(st, target)}")
