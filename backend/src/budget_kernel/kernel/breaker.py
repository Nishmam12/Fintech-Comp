"""Agent circuit breaker (ADR-0009 part B). Signatures are frozen; bodies arrive in Phase 3 step 6.

Until then every operation fails closed: nothing is suspended, reinstated or recorded.
"""
from __future__ import annotations


def record_signal(pool, *, grant_id, actor, kind: str, reason: str) -> dict:
    """Record an INJECTION strike for the grant holder; may suspend the grant. Returns {grant_id, strikes, suspended}."""
    raise NotImplementedError("circuit breaker: record_signal is implemented in Phase 3 step 6")


def suspend(pool, *, grant_id, actor) -> dict:
    """Manual suspend (owner or ancestor holder). Idempotent. Returns {grant_id, status, already}."""
    raise NotImplementedError("circuit breaker: suspend is implemented in Phase 3 step 6")


def reinstate(pool, *, grant_id, actor) -> dict:
    """suspended -> active (owner or ancestor holder); resets the strike count. Returns {grant_id, status}."""
    raise NotImplementedError("circuit breaker: reinstate is implemented in Phase 3 step 6")
