"""Pinned model routes (ADR-0006 / ROUTING_POLICY). Exact IDs only, never aliases.

Both routes run in NON-THINKING mode so `max_tokens` bounds every billable output token
(ADR-0006 worst-case rule). The extra_body switches below are provider-specific and are confirmed
by the live smoke test (OQ-005); until then a route that rejects them fails closed (4xx -> release).
"""
from __future__ import annotations

import os

from .adapter import ProviderConfig


def primary() -> ProviderConfig:
    return ProviderConfig(
        name="dashscope",
        base_url=os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
        api_key_env="DASHSCOPE_API_KEY",
        model_id="qwen3.7-flash-2026-07-15",
        extra_body={"enable_thinking": False},
    )


def escalation() -> ProviderConfig:
    """DeepSeek directly by default. BK_ESCALATION_PROVIDER=openrouter selects the same model family through
    OpenRouter (used for evaluation config C). OpenRouter switches thinking off with `reasoning.enabled=false`;
    DeepSeek's own `thinking` field is ignored there (checked live on 2026-10-19)."""
    if os.environ.get("BK_ESCALATION_PROVIDER", "").strip().lower() == "openrouter":
        return ProviderConfig(
            name="openrouter",
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key_env="OPENROUTER_API_KEY",
            model_id="deepseek/deepseek-v4.1-flash",
            extra_body={"reasoning": {"enabled": False}},
        )
    return ProviderConfig(
        name="deepseek",
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key_env="DEEPSEEK_API_KEY",
        model_id="deepseek-flash",
        extra_body={"thinking": {"type": "disabled"}},
    )
