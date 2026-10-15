"""Grant scope: validation and the attenuation (subset) rule from ADR-0004 / ADR-0008."""
from __future__ import annotations

from typing import Any

from .errors import ValidationFailed

_REQUIRED = {"categories", "recipients", "per_tx_limit", "can_delegate"}
_OPTIONAL = {"window_limit", "window_seconds", "review_above"}   # ADR-0008: absent = control off
MAX_BIGINT = 2**63 - 1
MIN_WINDOW_SECONDS, MAX_WINDOW_SECONDS = 60, 30 * 24 * 3600


def _int(raw: dict, key: str, low: int, high: int) -> int:
    v = raw[key]
    if isinstance(v, bool) or not isinstance(v, int) or not low <= v <= high:
        raise ValidationFailed(f"scope.{key} must be an integer between {low} and {high}", code="BAD_SCOPE")
    return v


def validate_scope(raw: Any) -> dict:
    if not isinstance(raw, dict) or not _REQUIRED <= set(raw) or set(raw) - _REQUIRED - _OPTIONAL:
        raise ValidationFailed(f"scope must have the keys {sorted(_REQUIRED)} and may add {sorted(_OPTIONAL)}",
                               code="BAD_SCOPE")
    cats, recs = raw["categories"], raw["recipients"]
    for name, lst in (("categories", cats), ("recipients", recs)):
        if not isinstance(lst, list) or not lst or not all(isinstance(x, str) and x.strip() for x in lst):
            raise ValidationFailed(f"scope.{name} must be a non-empty list of strings", code="BAD_SCOPE")
    lim = raw["per_tx_limit"]
    if isinstance(lim, bool) or not isinstance(lim, int) or not 0 < lim <= MAX_BIGINT:
        raise ValidationFailed("scope.per_tx_limit must be a positive integer (minor units)", code="BAD_SCOPE")
    if not isinstance(raw["can_delegate"], bool):
        raise ValidationFailed("scope.can_delegate must be a boolean", code="BAD_SCOPE")
    out = {
        "categories": sorted({c.strip().lower() for c in cats}),
        "recipients": sorted({r.strip().lower() for r in recs}),
        "per_tx_limit": lim,
        "can_delegate": raw["can_delegate"],
    }
    # A window limit needs a window length and vice versa: half a velocity rule is a configuration error.
    if ("window_limit" in raw) != ("window_seconds" in raw):
        raise ValidationFailed("scope.window_limit and scope.window_seconds must be set together", code="BAD_SCOPE")
    if "window_limit" in raw:
        out["window_limit"] = _int(raw, "window_limit", 1, MAX_BIGINT)
        out["window_seconds"] = _int(raw, "window_seconds", MIN_WINDOW_SECONDS, MAX_WINDOW_SECONDS)
    if "review_above" in raw:
        out["review_above"] = _int(raw, "review_above", 0, MAX_BIGINT)
    return out


def is_subset(child: dict, parent: dict) -> bool:
    """True iff `child` is no wider than `parent` on every dimension.

    A child may omit window_limit / review_above even when the parent sets them: the kernel checks every
    grant on the request's path (ADR-0008), so the ancestor's control still binds. When the child does set
    one, it may not be looser than the parent's."""
    if not (
        set(child["categories"]) <= set(parent["categories"])
        and set(child["recipients"]) <= set(parent["recipients"])
        and child["per_tx_limit"] <= parent["per_tx_limit"]
        and (not child["can_delegate"] or parent["can_delegate"])
    ):
        return False
    if "window_limit" in child and "window_limit" in parent:
        # Stricter means: no larger limit over a window at least as long (the same cap over a LONGER window
        # binds harder; over a shorter one it would allow more spend per hour than the parent declared).
        if child["window_limit"] > parent["window_limit"] or child["window_seconds"] < parent["window_seconds"]:
            return False
    if "review_above" in child and "review_above" in parent and child["review_above"] > parent["review_above"]:
        return False
    return True
