"""Interpret a request, then let the deterministic kernel decide. Shared by the HTTP API and the
evaluation runner so both exercise exactly the same path.

The kernel receives plain values only (amount, currency, recipient, category) -- never the model's
proposal object as authority. Anything not cleanly resolved is held for review (no funds reserved);
an unresolved interpretation never reaches the kernel.
"""
from __future__ import annotations

from budget_kernel import kernel

from .interpret import interpret


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
            needs_review=interp["status"] == "needs_review", proposal=p)
    return {"interpretation": interp, "decision": decision}
