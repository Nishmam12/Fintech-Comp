"""Deterministic semantic checks on an untrusted proposal. No model is consulted here.

Amounts are re-derived from the user's own text with integer arithmetic (Decimal is used only to
parse the digits, never for float math). A proposed amount that cannot be explained by the text
-- directly, as a sum of mentioned amounts, or as a mentioned amount plus/minus a mentioned
percentage -- is flagged AMOUNT_UNGROUNDED and must go to review.
"""
from __future__ import annotations

import itertools
import re
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .schema import Proposal

_AMOUNT = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?![\d]|\.\d)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above)|disregard (the )?(rules|instructions|policy)|"
    r"system prompt|you are now|override|\bauthori[sz]ed\s*[:=]|approve (this|it) (automatically|regardless)|"
    r"bypass", re.I)
MAX_TEXT = 2_000


def amounts_in(text: str) -> list[int]:
    """Every numeric amount mentioned, in minor units (x100), excluding numbers that are percentages."""
    pct_spans = [m.span(1) for m in _PERCENT.finditer(text)]
    out = []
    for m in _AMOUNT.finditer(text):
        if any(s <= m.start(1) < e for s, e in pct_spans):
            continue
        whole = int(m.group(1).replace(",", ""))
        frac = (m.group(2) or "0").ljust(2, "0")
        out.append(whole * 100 + int(frac))
    return out


def percents_in(text: str) -> list[Decimal]:
    return [Decimal(m.group(1)) for m in _PERCENT.finditer(text)]


def grounded_amounts(text: str) -> set[int]:
    base = amounts_in(text)
    cands = set(base)
    for r in (2, 3):
        for combo in itertools.combinations(base[:8], r):
            cands.add(sum(combo))
    # A percentage may apply to a single mentioned amount or to a sum of them (e.g. "total incl. 5% fee").
    for a, p in itertools.product(sorted(cands)[:40], percents_in(text)[:4]):
        delta = Decimal(a) * p / Decimal(100)
        for rounding in (ROUND_FLOOR, ROUND_CEILING):
            d = int(delta.to_integral_value(rounding=rounding))
            cands.update({a + d, a - d})
    return {c for c in cands if c > 0}


def name_in_text(name: str | None, text: str) -> bool:
    """True iff `name` occurs in the user's text as a whole word (case-insensitive). Recipient and category
    decide where money goes and what it is for, so they must come from the text, never from the model's guess."""
    if not name or not name.strip():
        return False
    pattern = r"(?<![A-Za-z0-9])" + re.escape(name.strip()) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def injection_suspected(text: str) -> bool:
    return bool(_INJECTION.search(text))


def semantic_issues(p: Proposal, text: str) -> list[str]:
    """Stable issue codes. Any issue means the proposal cannot be auto-processed."""
    issues: list[str] = []
    low = text.lower()
    if p.request_type == "payment" and not p.complete and not p.missing_fields:
        issues.append("INCOMPLETE_WITHOUT_MISSING_FIELDS")
    if p.complete and p.amount_minor not in grounded_amounts(text):
        issues.append("AMOUNT_UNGROUNDED")
    if p.complete:
        if not name_in_text(p.recipient, text):
            issues.append("RECIPIENT_UNGROUNDED")
        if not name_in_text(p.category, text):
            issues.append("CATEGORY_UNGROUNDED")
    for ev in p.evidence:
        if ev.quote.lower() not in low:
            issues.append("EVIDENCE_NOT_IN_INPUT")
            break
    if p.conflicts:
        issues.append("CONFLICTS_REPORTED")
    if injection_suspected(text):
        issues.append("INJECTION_SUSPECTED")
    return issues
