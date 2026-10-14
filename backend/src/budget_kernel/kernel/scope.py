"""Grant scope: validation and the attenuation (subset) rule from ADR-0004."""
from __future__ import annotations

from typing import Any

from .errors import ValidationFailed

_KEYS = {"categories", "recipients", "per_tx_limit", "can_delegate"}
MAX_BIGINT = 2**63 - 1


def validate_scope(raw: Any) -> dict:
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ValidationFailed(f"scope must have exactly the keys {sorted(_KEYS)}", code="BAD_SCOPE")
    cats, recs = raw["categories"], raw["recipients"]
    for name, lst in (("categories", cats), ("recipients", recs)):
        if not isinstance(lst, list) or not lst or not all(isinstance(x, str) and x.strip() for x in lst):
            raise ValidationFailed(f"scope.{name} must be a non-empty list of strings", code="BAD_SCOPE")
    lim = raw["per_tx_limit"]
    if isinstance(lim, bool) or not isinstance(lim, int) or not 0 < lim <= MAX_BIGINT:
        raise ValidationFailed("scope.per_tx_limit must be a positive integer (minor units)", code="BAD_SCOPE")
    if not isinstance(raw["can_delegate"], bool):
        raise ValidationFailed("scope.can_delegate must be a boolean", code="BAD_SCOPE")
    return {
        "categories": sorted({c.strip().lower() for c in cats}),
        "recipients": sorted({r.strip().lower() for r in recs}),
        "per_tx_limit": lim,
        "can_delegate": raw["can_delegate"],
    }


def is_subset(child: dict, parent: dict) -> bool:
    """True iff `child` is no wider than `parent` on every dimension."""
    return (
        set(child["categories"]) <= set(parent["categories"])
        and set(child["recipients"]) <= set(parent["recipients"])
        and child["per_tx_limit"] <= parent["per_tx_limit"]
        and (not child["can_delegate"] or parent["can_delegate"])
    )
