"""Request bodies. Strict types, unknown fields rejected: a client (or model) cannot smuggle
trusted fields such as `authorized`, `state` or `reserved` into a request."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Scope(Strict):
    categories: list[str] = Field(min_length=1, max_length=50)
    recipients: list[str] = Field(min_length=1, max_length=200)
    per_tx_limit: StrictInt = Field(gt=0)
    can_delegate: StrictBool
    # ADR-0008: optional controls; absent means off. window_limit and window_seconds go together.
    window_limit: StrictInt | None = Field(default=None, gt=0)
    window_seconds: StrictInt | None = Field(default=None, ge=60, le=2_592_000)
    review_above: StrictInt | None = Field(default=None, ge=0)


class CreatePrincipal(Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["human", "agent", "service"]


class CreateMandate(Strict):
    currency: str = Field(min_length=3, max_length=3)
    total: StrictInt = Field(gt=0)
    protected_reserve: StrictInt = Field(ge=0)
    expires_at: datetime
    scope: Scope


class Delegate(Strict):
    parent_grant_id: str
    holder_principal_id: str
    amount: StrictInt = Field(gt=0)
    expires_at: datetime
    scope: Scope
    idempotency_key: str = Field(min_length=1, max_length=200)


class Authorize(Strict):
    grant_id: str
    amount: StrictInt = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    recipient: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    needs_review: StrictBool = False


class SettleFail(Strict):
    proof: str = Field(min_length=1, max_length=500)


class Review(Strict):
    approve: StrictBool


class Interpret(Strict):
    grant_id: str
    text: str = Field(min_length=1, max_length=2000)


class AgentRequest(Interpret):
    idempotency_key: str = Field(min_length=1, max_length=200)


class SimulationRun(Strict):
    scenario: str = Field(min_length=1, max_length=60)
