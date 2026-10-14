"""Database access. One short transaction per kernel operation.

Uses the Supabase *session* pooler (port 5432): the transaction pooler (6543)
does not support the session-level behaviour the kernel relies on.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from budget_kernel.config import Settings


@contextmanager
def transaction(settings: Settings, schema: str | None = None) -> Iterator[psycopg.Connection]:
    """Open a connection, pin search_path to `schema`, commit on success, roll back on error."""
    schema = schema or settings.schema
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=15) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        yield conn  # psycopg commits on clean exit of the connection context, rolls back on exception
