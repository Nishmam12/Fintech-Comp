"""Versioned rate card (ADR-0006). Integer micro-USD per million tokens; no floats, no secrets.

An unknown model, a missing field or an unverified entry makes the route unavailable: callers
must fail closed to the deterministic path or to pending human review.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "rate_card.json"
_REQUIRED = ("provider", "model_id", "region", "input_price_micro_per_Mtok", "cached_input_price_micro_per_Mtok",
             "output_price_micro_per_Mtok", "reasoning_billing", "fixed_fee_micro", "source_url", "accessed_on",
             "verified")


class RouteUnavailable(Exception):
    """No usable price for this model: do not dispatch a paid call."""


@dataclass(frozen=True)
class Rate:
    provider: str
    model_id: str
    price_in: int
    price_cached: int
    price_out: int
    reasoning_billing: str
    fixed_fee: int
    version: str
    tier_max_input_tokens: int | None = None  # price only valid while input stays within this tier


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def estimate_worst_case(rate: Rate, prompt_bytes: int, max_tokens: int) -> int:
    """UTF-8 byte length is a safe upper bound on BPE input tokens; max_tokens bounds output
    including reasoning (routes whose provider bills reasoning outside max_tokens are disallowed)."""
    if prompt_bytes < 0 or max_tokens <= 0:
        raise ValueError("prompt_bytes must be >= 0 and max_tokens > 0")
    if rate.tier_max_input_tokens is not None and prompt_bytes > rate.tier_max_input_tokens:
        # Tiered providers bill ALL tokens at the higher tier's price: refuse rather than under-reserve.
        raise RouteUnavailable(f"prompt may exceed the {rate.tier_max_input_tokens}-token price tier")
    return (_ceil_div(prompt_bytes * rate.price_in, 1_000_000)
            + _ceil_div(max_tokens * rate.price_out, 1_000_000) + rate.fixed_fee) or 1


def actual_cost(prices: dict, usage: dict) -> int:
    """Cost from provider usage fields with the prices frozen on the call row."""
    inp, cached = int(usage["input_tokens"]), int(usage.get("cached_tokens") or 0)
    out, reasoning = int(usage["output_tokens"]), int(usage.get("reasoning_tokens") or 0)
    if min(inp, cached, out, reasoning) < 0 or cached > inp:
        raise ValueError("implausible usage numbers")
    billable_out = out + (reasoning if prices["reasoning_billing"] == "separate" else 0)
    return (_ceil_div((inp - cached) * prices["price_in_micro_per_mtok"], 1_000_000)
            + _ceil_div(cached * prices["price_cached_micro_per_mtok"], 1_000_000)
            + _ceil_div(billable_out * prices["price_out_micro_per_mtok"], 1_000_000)
            + prices["fixed_fee_micro"])


class RateCard:
    def __init__(self, entries: list[dict], version: str):
        self.version = version
        self._by_key: dict[tuple[str, str], dict] = {}
        for e in entries:
            if any(k not in e for k in _REQUIRED):
                continue  # incomplete entry: model stays unavailable
            self._by_key[(e["provider"], e["model_id"])] = e

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PATH) -> "RateCard":
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        return cls(data.get("models", []), data.get("version") or hashlib.sha256(raw).hexdigest()[:12])

    def rate(self, provider: str, model_id: str) -> Rate:
        e = self._by_key.get((provider, model_id))
        if e is None:
            raise RouteUnavailable(f"no rate card entry for {provider}/{model_id}")
        if e["verified"] is not True:
            raise RouteUnavailable(f"price for {provider}/{model_id} not verified from an official source")
        ints = [e["input_price_micro_per_Mtok"], e["cached_input_price_micro_per_Mtok"],
                e["output_price_micro_per_Mtok"], e["fixed_fee_micro"]]
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in ints):
            raise RouteUnavailable(f"prices for {provider}/{model_id} must be non-negative integers")
        if e["reasoning_billing"] not in ("as_output", "separate", "none"):
            raise RouteUnavailable(f"unknown reasoning_billing for {provider}/{model_id}")
        tier = e.get("tier_max_input_tokens")
        if tier is not None and (isinstance(tier, bool) or not isinstance(tier, int) or tier <= 0):
            raise RouteUnavailable(f"bad tier_max_input_tokens for {provider}/{model_id}")
        return Rate(provider, model_id, *ints[:3], e["reasoning_billing"], ints[3], self.version, tier)
