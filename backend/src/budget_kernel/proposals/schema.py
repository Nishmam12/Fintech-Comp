"""Typed, UNTRUSTED proposal (ADR-0001). A model may fill this in; it carries no authorization state.

`extra="forbid"` means a model (or injected text) that emits `authorized`, `approved`, `state`,
`balance` or any other unknown key makes the whole proposal invalid. The kernel never reads
anything from a proposal except the plain values the caller extracts after validation.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

SCHEMA_VERSION = "1"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(Strict):
    field: Literal["amount", "currency", "recipient", "category", "purpose"]
    quote: str = Field(min_length=1, max_length=200)   # must be a substring of the user's text


class Proposal(Strict):
    schema_version: Literal["1"]
    request_type: Literal["payment", "clarification", "unsupported"]
    amount_minor: StrictInt | None = Field(default=None, gt=0, le=10**12)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    recipient: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    purpose: str | None = Field(default=None, max_length=200)
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)
    missing_fields: list[str] = Field(default_factory=list, max_length=8)
    ambiguities: list[str] = Field(default_factory=list, max_length=8)
    conflicts: list[str] = Field(default_factory=list, max_length=8)
    needs_human_review: StrictBool = False
    explanation: str = Field(default="", max_length=300)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v):
        return v.upper() if v else v

    @property
    def complete(self) -> bool:
        return (self.request_type == "payment" and None not in (self.amount_minor, self.currency, self.recipient,
                                                                self.category) and not self.missing_fields)


PROPOSAL_JSON_EXAMPLE = (
    '{"schema_version":"1","request_type":"payment","amount_minor":12000,"currency":"USD","recipient":"aws",'
    '"category":"cloud","purpose":"monthly hosting","evidence":[{"field":"amount","quote":"$120"}],'
    '"missing_fields":[],"ambiguities":[],"conflicts":[],"needs_human_review":false,"explanation":"..."}'
)
