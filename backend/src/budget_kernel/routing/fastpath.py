"""Deterministic fast path (no paid inference). Applies ONLY when the input is fully resolvable by
explicit, tested rules; otherwise returns None and the router decides about a model.

Two shapes are accepted:
1. A structured JSON object with exactly the proposal fields (already typed).
2. The canonical sentence  "pay <amount> <CUR> to <recipient> for <category>"  where recipient and
   category are names the grant's scope already lists. Anything else is NOT guessed.
"""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from budget_kernel.proposals.schema import SCHEMA_VERSION, Proposal
from budget_kernel.proposals.validate import injection_suspected

_SENTENCE = re.compile(
    r"^\s*(?:please\s+)?(?:pay|send|transfer)\s+\$?(?P<amount>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d{1,2}))?\s*"
    r"(?P<cur>[A-Za-z]{3})?\s+to\s+(?P<recipient>[A-Za-z0-9_.\- ]{1,60}?)\s+for\s+(?P<category>[A-Za-z0-9_.\- ]{1,60}?)\s*\.?\s*$",
    re.I)
_SYMBOLS = {"$": "USD"}


def try_fast_path(text: str, *, known_recipients: set[str], known_categories: set[str],
                  default_currency: str) -> Proposal | None:
    if injection_suspected(text):
        return None
    return _structured(text) or _sentence(text, known_recipients, known_categories, default_currency)


def _structured(text: str) -> Proposal | None:
    s = text.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        return Proposal.model_validate_json(s)
    except (ValidationError, ValueError):
        return None


def _sentence(text, recipients, categories, default_currency) -> Proposal | None:
    m = _SENTENCE.match(text)
    if not m:
        return None
    recipient, category = m["recipient"].strip().lower(), m["category"].strip().lower()
    if recipient not in recipients or category not in categories:
        return None                      # unknown names are never guessed
    cur = (m["cur"] or ("USD" if "$" in text else default_currency)).upper()
    minor = int(m["amount"].replace(",", "")) * 100 + int((m["frac"] or "0").ljust(2, "0"))
    if minor <= 0:
        return None
    return Proposal(schema_version=SCHEMA_VERSION, request_type="payment", amount_minor=minor, currency=cur,
                    recipient=recipient, category=category, explanation="matched the canonical payment sentence")
