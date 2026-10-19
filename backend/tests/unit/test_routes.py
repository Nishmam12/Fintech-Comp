"""Escalation route selection (config C) and its rate card entry. No database, no network."""
from __future__ import annotations

from budget_kernel.costledger.rate_card import RateCard
from budget_kernel.providers import routes


def test_escalation_defaults_to_deepseek_direct(monkeypatch):
    monkeypatch.delenv("BK_ESCALATION_PROVIDER", raising=False)
    cfg = routes.escalation()
    assert (cfg.name, cfg.model_id, cfg.api_key_env) == ("deepseek", "deepseek-flash", "DEEPSEEK_API_KEY")
    assert cfg.extra_body == {"thinking": {"type": "disabled"}}


def test_openrouter_escalation_is_opt_in_and_disables_thinking(monkeypatch):
    monkeypatch.setenv("BK_ESCALATION_PROVIDER", "openrouter")
    cfg = routes.escalation()
    assert (cfg.name, cfg.model_id, cfg.api_key_env) == ("openrouter", "deepseek/deepseek-v4.1-flash", "OPENROUTER_API_KEY")
    # OpenRouter ignores DeepSeek's own switch; this one is what makes max_tokens bound the bill.
    assert cfg.extra_body == {"reasoning": {"enabled": False}}


def test_every_route_has_a_conservative_verified_price(monkeypatch):
    card = RateCard.load()
    primary = routes.primary()
    monkeypatch.delenv("BK_ESCALATION_PROVIDER", raising=False)
    direct = routes.escalation()
    monkeypatch.setenv("BK_ESCALATION_PROVIDER", "openrouter")
    via_router = routes.escalation()
    for cfg in (primary, direct, via_router):
        rate = card.rate(cfg.name, cfg.model_id)           # raises RouteUnavailable if missing or unverified
        assert rate.price_in > 0 and rate.price_out > 0
    # The OpenRouter route is priced at DeepSeek's own peak prices, never below them.
    d, o = card.rate(direct.name, direct.model_id), card.rate(via_router.name, via_router.model_id)
    assert (o.price_in, o.price_out) >= (d.price_in, d.price_out)
