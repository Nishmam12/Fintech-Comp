"""The single serialization point for kernel writes (ADR-0005 section 1).

Every state-changing operation runs inside `kernel_tx`: one DB transaction that takes the
mandate row lock first, then sweeps expired state, then lets the operation run. A lock or
statement timeout surfaces as KernelBusy (retryable), never as an approval.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import psycopg
from psycopg.types.json import Jsonb

from .errors import KernelBusy, NotFound

import os

RESERVE_TTL_SECONDS = 15 * 60
# Waiters give up (KernelBusy, retryable) rather than queue forever. Raise for heavy concurrency tests.
LOCK_TIMEOUT_MS = int(os.environ.get("BK_LOCK_TIMEOUT_MS", "3000"))


@dataclass
class Ctx:
    conn: psycopg.Connection
    mandate: dict

    @property
    def mandate_id(self) -> uuid.UUID:
        return self.mandate["id"]


def audit(conn: psycopg.Connection, mandate_id, kind: str, actor=None, subject=None, **detail: Any) -> None:
    conn.execute(
        "INSERT INTO audit_events(mandate_id, kind, actor_principal_id, subject_id, detail)"
        " VALUES (%s, %s, %s, %s, %s)",
        (mandate_id, kind, actor, subject, Jsonb(detail)),
    )


def movement(conn, mandate_id, kind, amount, *, from_grant=None, from_bucket=None, to_grant=None,
             to_bucket=None, transaction_id=None, actor=None) -> None:
    if amount <= 0:
        return
    conn.execute(
        "INSERT INTO ledger_movements(mandate_id, kind, amount, from_grant_id, from_bucket, to_grant_id,"
        " to_bucket, transaction_id, actor_principal_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (mandate_id, kind, amount, from_grant, from_bucket, to_grant, to_bucket, transaction_id, actor),
    )


def mandate_of_grant(pool, grant_id) -> uuid.UUID:
    """Immutable lookup done before taking the lock (ADR-0005)."""
    with pool.connection() as conn:
        row = conn.execute("SELECT mandate_id FROM grants WHERE id = %s", (grant_id,)).fetchone()
    if row is None:
        raise NotFound("grant not found", code="GRANT_NOT_FOUND")
    return row["mandate_id"]


def mandate_of_tx(pool, tx_id) -> uuid.UUID:
    with pool.connection() as conn:
        row = conn.execute("SELECT mandate_id FROM transactions WHERE id = %s", (tx_id,)).fetchone()
    if row is None:
        raise NotFound("transaction not found", code="TX_NOT_FOUND")
    return row["mandate_id"]


@contextmanager
def kernel_tx(pool, mandate_id) -> Iterator[Ctx]:
    from .sweep import sweep  # local import: sweep uses this module's helpers

    try:
        with pool.connection() as conn:
            with conn.transaction():
                conn.execute(f"SET LOCAL lock_timeout = '{int(LOCK_TIMEOUT_MS)}ms'")
                conn.execute("SET LOCAL statement_timeout = '8s'")
                mandate = conn.execute(
                    "SELECT * FROM mandates WHERE id = %s FOR UPDATE", (mandate_id,)
                ).fetchone()
                if mandate is None:
                    raise NotFound("mandate not found", code="MANDATE_NOT_FOUND")
                ctx = Ctx(conn, mandate)
                sweep(ctx)
                yield ctx
    except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled) as exc:
        raise KernelBusy("mandate is busy, retry") from exc
