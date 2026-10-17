"""Deterministic semantic checks on an untrusted proposal. No model is consulted here.

Amounts are re-derived from the user's own text with integer arithmetic (Decimal is used only to
parse the digits, never for float math). A proposed amount that cannot be explained by the text
-- directly, as a sum of mentioned amounts, or as a mentioned amount plus/minus a mentioned
percentage -- is flagged AMOUNT_UNGROUNDED and must go to review.
"""
from __future__ import annotations

import itertools
import json
import os
import re
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

from .schema import Proposal

_AMOUNT = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?![\d]|\.\d)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above)|disregard (the )?(rules|instructions|policy)|"
    r"system prompt|you are now|override|\bauthori[sz]ed\s*[:=]|approve (this|it) (automatically|regardless)|"
    r"bypass", re.I)
MAX_TEXT = 2_000

# --- number words (ADR-0009 D2). "forty dollars" is an amount only WITH a currency word after it, so a stray "one"
# or "a" can never ground an amount. Cardinals up to 999,999; anything malformed is ignored (fail closed).
_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1000}
_NUMWORD = "|".join(sorted([*_UNITS, *_TENS, *_SCALES], key=len, reverse=True))
_WORD_AMOUNT = re.compile(
    rf"(?<![A-Za-z0-9])((?:a|{_NUMWORD})(?:[\s-]+(?:and|a|{_NUMWORD}))*)\s+(dollars?|usd|bucks?|cents?)(?![A-Za-z])", re.I)


def _words_to_int(phrase: str) -> int | None:
    """Value of an English cardinal phrase, or None if it is not a well-formed one (0 < value <= 999,999)."""
    toks = [t for t in re.split(r"[\s-]+", phrase.lower()) if t]
    total, cur, prev, saw_number = 0, 0, None, False
    for i, t in enumerate(toks):
        if t == "a":
            if i != 0 or len(toks) < 2 or toks[1] not in _SCALES:
                return None
            cur, prev, saw_number = 1, "a", True
        elif t == "and":
            if prev not in ("hundred", "thousand") or i == len(toks) - 1:
                return None
            prev = "and"
        elif t in _UNITS:
            if prev in ("unit", "a") or (prev == "tens" and not 1 <= _UNITS[t] <= 9) or (prev is None and len(toks) > 1 and _UNITS[t] == 0):
                return None
            cur, prev, saw_number = cur + _UNITS[t], ("unit" if prev != "tens" else "unit"), True
        elif t in _TENS:
            if prev not in (None, "hundred", "thousand", "and"):
                return None
            cur, prev, saw_number = cur + _TENS[t], "tens", True
        elif t == "hundred":
            if prev not in ("unit", "a") or cur >= 100 or (prev == "unit" and cur > 19):
                return None
            cur, prev = cur * 100, "hundred"
        elif t == "thousand":
            if prev not in ("unit", "tens", "hundred", "a") or total != 0 or cur == 0 or cur >= 1000:
                return None
            total, cur, prev = cur * 1000, 0, "thousand"
        else:
            return None
    value = total + cur
    return value if saw_number and 0 < value <= 999_999 else None

# --- recipient aliases (ADR-0009 D2): operator-controlled, loaded from a file, never from the model.
DEFAULT_ALIASES_PATH = Path(__file__).resolve().parents[3] / "config" / "recipient_aliases.json"
_ALIAS_CACHE: tuple[tuple[str, int], dict[str, list[str]]] | None = None


def _aliases() -> dict[str, list[str]]:
    """{canonical name (lowercase): [alias phrase, ...]}. Re-read when the file changes. A missing or malformed file
    means NO aliases (stricter), never an error."""
    global _ALIAS_CACHE
    path = Path(os.environ.get("BK_RECIPIENT_ALIASES") or DEFAULT_ALIASES_PATH)
    try:
        key = (str(path), path.stat().st_mtime_ns)
        if _ALIAS_CACHE and _ALIAS_CACHE[0] == key:
            return _ALIAS_CACHE[1]
        raw = json.loads(path.read_text(encoding="utf-8"))
        ok = isinstance(raw, dict) and all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(a, str) and a.strip() for a in v) for k, v in raw.items())
        data = {k.strip().lower(): [" ".join(a.lower().split()) for a in v] for k, v in raw.items()} if ok else {}
    except (OSError, ValueError):
        return {}
    _ALIAS_CACHE = (key, data)
    return data


def amounts_in(text: str) -> list[int]:
    """Every numeric amount mentioned, in minor units (x100), excluding numbers that are percentages."""
    pct_spans = [m.span(1) for m in _PERCENT.finditer(text)]
    found: list[tuple[int, int]] = []
    for m in _AMOUNT.finditer(text):
        if any(s <= m.start(1) < e for s, e in pct_spans):
            continue
        whole = int(m.group(1).replace(",", ""))
        frac = (m.group(2) or "0").ljust(2, "0")
        found.append((m.start(1), whole * 100 + int(frac)))
    for m in _WORD_AMOUNT.finditer(text):          # "forty dollars", "fifty cents" (never without the currency word)
        value = _words_to_int(m.group(1))
        if value is not None:
            found.append((m.start(1), value if m.group(2).lower().startswith("cent") else value * 100))
    return [v for _, v in sorted(found)]


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
    phrases = [" ".join(name.split())] + _aliases().get(name.strip().lower(), [])
    for phrase in phrases:
        pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


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
