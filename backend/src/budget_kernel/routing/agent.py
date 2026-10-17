"""Interpret a request, then let the deterministic kernel decide. Shared by the HTTP API and the
evaluation runner so both exercise exactly the same path.

The kernel receives plain values only (amount, currency, recipient, category) -- never the model's
proposal object as authority. Anything not cleanly resolved is held for review (no funds reserved);
an unresolved interpretation never reaches the kernel.
"""
from __future__ import annotations

import hashlib

from budget_kernel import kernel

from .interpret import interpret

TEXT_HASH_KEY = "request_text_sha256"   # display-only marker stored with the proposal; the kernel never reads it


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def stored_replay(pool, *, grant_id, idempotency_key: str, text: str) -> dict | None:
    """BK-305 (closes R9): the decision already stored for (grant, idempotency key), or None. Runs BEFORE any model
    call, so a retry costs no inference. Read-only; the caller has already checked the holder. If the key exists but
    the text is not provably the same request, it is a conflict -- never re-interpret."""
    with pool.connection() as c:
        tx = c.execute("SELECT id, state, reject_reason, review_reason, proposal FROM transactions"
                       " WHERE grant_id = %s AND idempotency_key = %s", (grant_id, idempotency_key)).fetchone()
    if tx is None:
        return None
    prop = dict(tx["proposal"] or {})
    if prop.pop(TEXT_HASH_KEY, None) != text_hash(text):
        raise kernel.IdempotencyConflict("idempotency key reused with a different request")
    return {"interpretation": {"status": "needs_review" if tx["review_reason"] else "ok", "proposal": prop,
                               "reasons": [], "trail": [], "replayed": True},
            "decision": {"transaction_id": tx["id"], "state": tx["state"], "reason": tx["reject_reason"],
                         "review_reason": tx["review_reason"], "replayed": True}}


def interpret_then_decide(pool, card, *, grant_id, actor, text: str, idempotency_key: str, recipients, categories,
                          currency: str, transport=None, **interpret_kwargs) -> dict:
    interp = interpret(pool, card, text, recipients=recipients, categories=categories, currency=currency,
                       transport=transport, **interpret_kwargs)
    p, decision = interp["proposal"], None
    if (interp["status"] in ("ok", "needs_review") and p and p["request_type"] == "payment" and not p["missing_fields"]
            and None not in (p["amount_minor"], p["currency"], p["recipient"], p["category"])):
        decision = kernel.authorize(
            pool, grant_id=grant_id, actor=actor, amount=p["amount_minor"], currency=p["currency"],
            recipient=p["recipient"], category=p["category"], idempotency_key=idempotency_key,
            needs_review=interp["status"] == "needs_review", proposal={**p, TEXT_HASH_KEY: text_hash(text)})
    return {"interpretation": interp, "decision": decision}
