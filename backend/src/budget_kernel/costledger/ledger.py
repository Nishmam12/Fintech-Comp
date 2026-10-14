"""Inference cost ledger (ADR-0006): reserve worst case before dispatch, reconcile after.

Lock order everywhere: inference_calls row (if any) first, then budget_buckets rows in
alphabetical bucket order. Never called inside a kernel (mandate-lock) transaction.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

from psycopg.types.json import Jsonb

from .rate_card import Rate, actual_cost

ROUTES = ("primary", "escalation", "retries", "eval")
STALE_AFTER = timedelta(minutes=10)


class BudgetExhausted(Exception):
    """No paid call may be made. Callers fall back to the deterministic path or pending review;
    this is never a reason to approve anything (ADR-0001)."""


def default_caps() -> dict[str, int]:
    return {
        "global": int(os.environ.get("BK_GLOBAL_MONTHLY_CAP_MICRO_USD", "9500000")),
        "primary": 2_500_000, "escalation": 4_000_000, "retries": 2_000_000, "eval": 1_000_000,
    }


def _month(conn) -> date:
    return conn.execute("SELECT date_trunc('month', now() AT TIME ZONE 'UTC')::date AS m").fetchone()["m"]


def _lock_buckets(conn, month: date, buckets: set[str]) -> None:
    rows = conn.execute("SELECT bucket FROM budget_buckets WHERE month = %s AND bucket = ANY(%s)"
                        " ORDER BY bucket FOR UPDATE", (month, sorted(buckets))).fetchall()
    if len(rows) != len(buckets):
        raise RuntimeError(f"budget rows missing for {month}: {sorted(buckets)}")


def reserve(pool, *, route: str, rate: Rate, est_micro: int, purpose: str = "interpret",
            month: date | None = None, caps: dict[str, int] | None = None) -> dict:
    """Atomically reserve `est_micro` on ('global', route). Raises BudgetExhausted if either cap
    would be exceeded. `month`/`caps` are injectable for tests (ADR-0006 rollover test)."""
    if route not in ROUTES:
        raise ValueError(f"unknown route bucket {route!r}")
    if isinstance(est_micro, bool) or not isinstance(est_micro, int) or est_micro <= 0:
        raise ValueError("est_micro must be a positive integer")
    caps = caps or default_caps()
    with pool.connection() as conn:
        with conn.transaction():
            m = month or _month(conn)
            _sweep_stale(conn)
            # Create every bucket row for the month at once: reconciliation may need 'retries' (overruns)
            # even when no retry was ever reserved that month.
            for b in ("global",) + ROUTES:
                conn.execute("INSERT INTO budget_buckets(month, bucket, cap_micro_usd) VALUES (%s,%s,%s)"
                             " ON CONFLICT DO NOTHING", (m, b, caps[b]))
            _lock_buckets(conn, m, {"global", route})
            n = conn.execute(
                "UPDATE budget_buckets SET reserved_micro = reserved_micro + %s"
                " WHERE month = %s AND bucket = ANY(%s) AND reserved_micro + spent_micro + %s <= cap_micro_usd",
                (est_micro, m, ["global", route], est_micro)).rowcount
            if n != 2:
                raise BudgetExhausted(f"{route} or global budget for {m} cannot cover {est_micro} micro-USD")
            return conn.execute(
                "INSERT INTO inference_calls(id, month, route_bucket, provider, model_id, rate_card_version,"
                " price_in_micro_per_mtok, price_cached_micro_per_mtok, price_out_micro_per_mtok, reasoning_billing,"
                " fixed_fee_micro, est_micro, status, purpose) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved',%s)"
                " RETURNING *",
                (uuid.uuid4(), m, route, rate.provider, rate.model_id, rate.version, rate.price_in, rate.price_cached,
                 rate.price_out, rate.reasoning_billing, rate.fixed_fee, est_micro, purpose)).fetchone()


def mark_dispatched(pool, call_id) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE inference_calls SET status = 'dispatched', dispatched_at = clock_timestamp()"
                     " WHERE id = %s AND status = 'reserved'", (call_id,))


def reconcile(pool, call_id, usage: dict | None) -> dict:
    """Settle a call from provider usage. Missing/unparseable usage -> charged at worst case."""
    with pool.connection() as conn:
        with conn.transaction():
            call = conn.execute("SELECT * FROM inference_calls WHERE id = %s FOR UPDATE", (call_id,)).fetchone()
            if call is None:
                raise LookupError("unknown inference call")
            if call["status"] not in ("reserved", "dispatched"):
                return call  # idempotent
            actual = None
            if usage is not None:
                try:
                    actual = actual_cost(call, usage)
                except (KeyError, TypeError, ValueError):
                    actual = None
            return _charge(conn, call, actual, usage)


def release(pool, call_id) -> dict:
    """Provider error BEFORE any generation (connection refused, 4xx). A timeout is not this case."""
    with pool.connection() as conn:
        with conn.transaction():
            call = conn.execute("SELECT * FROM inference_calls WHERE id = %s FOR UPDATE", (call_id,)).fetchone()
            if call is None or call["status"] not in ("reserved", "dispatched"):
                return call
            _lock_buckets(conn, call["month"], {"global", call["route_bucket"]})
            conn.execute("UPDATE budget_buckets SET reserved_micro = reserved_micro - %s"
                         " WHERE month = %s AND bucket = ANY(%s)",
                         (call["est_micro"], call["month"], ["global", call["route_bucket"]]))
            return conn.execute("UPDATE inference_calls SET status = 'released', reconciled_at = clock_timestamp()"
                                " WHERE id = %s RETURNING *", (call_id,)).fetchone()


def _charge(conn, call: dict, actual: int | None, usage: dict | None) -> dict:
    est, route, m = call["est_micro"], call["route_bucket"], call["month"]
    overrun = max(0, actual - est) if actual is not None else 0
    _lock_buckets(conn, m, {"global", route} | ({"retries"} if overrun else set()))
    conn.execute("UPDATE budget_buckets SET reserved_micro = reserved_micro - %s, spent_micro = spent_micro + %s"
                 " WHERE month = %s AND bucket = ANY(%s)",
                 (est, est if actual is None else min(actual, est), m, ["global", route]))
    if overrun:
        # Overruns are charged to global and the retries/overrun bucket (once each, whatever the route).
        conn.execute("UPDATE budget_buckets SET spent_micro = spent_micro + %s WHERE month = %s AND bucket = ANY(%s)",
                     (overrun, m, ["global", "retries"]))
        conn.execute("INSERT INTO audit_events(mandate_id, kind, subject_id, detail) VALUES (NULL, 'COST_OVERRUN', %s, %s)",
                     (call["id"], Jsonb({"est_micro": est, "actual_micro": actual, "overrun_micro": overrun,
                                         "model_id": call["model_id"]})))
    u = usage or {}
    return conn.execute(
        "UPDATE inference_calls SET status = %s, actual_micro = %s, overrun_micro = %s, input_tokens = %s,"
        " output_tokens = %s, reasoning_tokens = %s, cached_tokens = %s, reconciled_at = clock_timestamp()"
        " WHERE id = %s RETURNING *",
        ("reconciled" if actual is not None else "charged_worst_case", actual if actual is not None else est, overrun,
         u.get("input_tokens"), u.get("output_tokens"), u.get("reasoning_tokens"), u.get("cached_tokens"),
         call["id"])).fetchone()


def _sweep_stale(conn) -> int:
    """Calls stuck in reserved/dispatched for >10 min are charged at worst case, never released:
    the provider may have billed (ADR-0006, crash between reserve and reconcile).
    Ordered by month so bucket locks are always taken in (month, bucket) order: no deadlocks."""
    stale = conn.execute(
        "SELECT * FROM inference_calls WHERE status IN ('reserved','dispatched') AND created_at < clock_timestamp() - %s"
        " ORDER BY month, id FOR UPDATE SKIP LOCKED", (STALE_AFTER,)).fetchall()
    for call in stale:
        _charge(conn, call, None, None)
    return len(stale)


def sweep_stale(pool) -> int:
    with pool.connection() as conn:
        with conn.transaction():
            return _sweep_stale(conn)


def snapshot(pool, month: date | None = None) -> dict:
    """Budget meter for the dashboard: caps, reserved, spent and remaining per bucket (micro-USD)."""
    with pool.connection() as conn:
        m = month or _month(conn)
        rows = conn.execute("SELECT bucket, cap_micro_usd, reserved_micro, spent_micro FROM budget_buckets"
                            " WHERE month = %s ORDER BY bucket", (m,)).fetchall()
    return {"month": m.isoformat(), "buckets": [
        {**r, "remaining_micro": r["cap_micro_usd"] - r["reserved_micro"] - r["spent_micro"]} for r in rows]}
