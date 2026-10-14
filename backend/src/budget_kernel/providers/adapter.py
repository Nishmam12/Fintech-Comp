"""Provider-independent chat adapter for OpenAI-compatible endpoints (DashScope, DeepSeek, OpenRouter).

Bounded by construction: one request, a hard timeout, max_tokens always sent, no automatic retries
(retries are a router decision because each one is a separate paid, reserved call). Credentials are
read from the environment at call time and never appear in exceptions, logs or return values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)


@dataclass(frozen=True)
class ProviderConfig:
    name: str                      # matches rate card "provider"
    base_url: str
    api_key_env: str
    model_id: str                  # pinned; aliases are never used
    extra_body: dict = field(default_factory=dict)   # e.g. disable thinking, per provider


class ProviderError(Exception):
    """`charge` tells the cost ledger how to settle the reservation:
    - 'release': failed before the provider could have generated anything (no key, connect error, 4xx)
    - 'worst_case': the request may have been processed (timeout, 5xx, bad body) -> charge the estimate"""

    def __init__(self, message: str, *, charge: str):
        super().__init__(message)
        self.charge = charge


@dataclass(frozen=True)
class ChatResult:
    text: str
    usage: dict | None
    finish_reason: str | None


def chat_json(cfg: ProviderConfig, system: str, user: str, *, max_tokens: int,
              transport: httpx.BaseTransport | None = None) -> ChatResult:
    key = os.environ.get(cfg.api_key_env, "").strip()
    if not key:
        raise ProviderError(f"{cfg.api_key_env} is not configured", charge="release")
    body = {
        "model": cfg.model_id,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        **cfg.extra_body,
    }
    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            r = client.post(f"{cfg.base_url.rstrip('/')}/chat/completions", json=body,
                            headers={"Authorization": f"Bearer {key}"})
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        raise ProviderError("could not connect to provider", charge="release") from None
    except httpx.HTTPError:
        raise ProviderError("provider request failed after sending", charge="worst_case") from None
    if 400 <= r.status_code < 500:
        raise ProviderError(f"provider rejected the request ({r.status_code})", charge="release")
    if r.status_code >= 500:
        raise ProviderError(f"provider error ({r.status_code})", charge="worst_case")
    try:
        data = r.json()
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("unparseable provider response", charge="worst_case") from None
    return ChatResult(text=text, usage=_usage(data.get("usage")), finish_reason=choice.get("finish_reason"))


def _usage(u: dict | None) -> dict | None:
    """Normalise OpenAI-style usage. Missing/odd -> None so the ledger charges worst case."""
    if not isinstance(u, dict):
        return None
    try:
        details_out = u.get("completion_tokens_details") or {}
        details_in = u.get("prompt_tokens_details") or {}
        return {
            "input_tokens": int(u["prompt_tokens"]),
            "output_tokens": int(u["completion_tokens"]),
            "reasoning_tokens": int(details_out.get("reasoning_tokens") or 0),
            "cached_tokens": int(details_in.get("cached_tokens") or u.get("prompt_cache_hit_tokens") or 0),
        }
    except (KeyError, TypeError, ValueError):
        return None
