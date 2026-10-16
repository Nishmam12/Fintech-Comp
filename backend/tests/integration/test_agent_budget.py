"""BK-304 (ADR-0009 D1): per-agent monthly inference budget, all-or-none with global and the route bucket."""
from __future__ import annotations

import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from budget_kernel.costledger import ledger
from budget_kernel.costledger.rate_card import Rate, RateCard
from budget_kernel.routing.interpret import interpret
from tests.integration.test_cost_ledger import RATE, SMALL, buckets, month  # noqa: F401  (month is a fixture)


def test_reserve_reconcile_and_release_move_all_three_buckets(pool, month):
    me = uuid.uuid4()
    a = ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=SMALL, principal_id=me, principal_cap=500)
    b = buckets(pool, month)
    key = f"principal:{me}"
    assert [b[k]["reserved_micro"] for k in ("global", "primary", key)] == [100, 100, 100] and b[key]["cap_micro_usd"] == 500
    ledger.reconcile(pool, a["id"], {"input_tokens": 20, "output_tokens": 10})        # actual 40
    b = buckets(pool, month)
    assert [(b[k]["reserved_micro"], b[k]["spent_micro"]) for k in ("global", "primary", key)] == [(0, 40)] * 3
    c = ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=SMALL, principal_id=me, principal_cap=500)
    ledger.release(pool, c["id"])
    b = buckets(pool, month)
    assert [(b[k]["reserved_micro"], b[k]["spent_micro"]) for k in ("global", "primary", key)] == [(0, 40)] * 3


def test_agent_cap_binds_first_and_leaves_no_partial_reservation(pool, month):
    me = uuid.uuid4()
    ledger.reserve(pool, route="primary", rate=RATE, est_micro=80, month=month, caps=SMALL, principal_id=me, principal_cap=100)
    with pytest.raises(ledger.AgentBudgetExhausted):
        ledger.reserve(pool, route="primary", rate=RATE, est_micro=30, month=month, caps=SMALL, principal_id=me, principal_cap=100)
    b = buckets(pool, month)
    assert (b["global"]["reserved_micro"], b["primary"]["reserved_micro"], b[f"principal:{me}"]["reserved_micro"]) == (80, 80, 80)
    other = uuid.uuid4()                                       # another agent is unaffected by this one's cap
    ledger.reserve(pool, route="primary", rate=RATE, est_micro=30, month=month, caps=SMALL, principal_id=other, principal_cap=100)


def test_route_cap_binding_does_not_leave_the_agent_bucket_charged(pool, month):
    me = uuid.uuid4()
    with pytest.raises(ledger.BudgetExhausted) as e:
        ledger.reserve(pool, route="eval", rate=RATE, est_micro=250, month=month, caps=SMALL, principal_id=me, principal_cap=1_000)
    assert not isinstance(e.value, ledger.AgentBudgetExhausted)
    b = buckets(pool, month)
    assert all(r["reserved_micro"] == 0 for r in b.values())       # nothing reserved anywhere (the attempt rolled back)


def test_concurrent_reservations_never_exceed_the_agent_cap(pool, month):
    me = uuid.uuid4()
    caps = {**SMALL, "global": 10_000, "primary": 10_000}

    def go(_):
        try:
            ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=caps, principal_id=me, principal_cap=1_000)
            return 1
        except ledger.AgentBudgetExhausted:
            return 0

    with ThreadPoolExecutor(8) as ex:
        won = sum(ex.map(go, range(40)))
    b = buckets(pool, month)
    key = f"principal:{me}"
    assert won == 10 and b[key]["reserved_micro"] == 1_000 == b["global"]["reserved_micro"] == b["primary"]["reserved_micro"]


def test_exhausted_agent_ends_unresolved_and_the_model_is_never_called(pool, monkeypatch):
    import httpx
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setenv("BK_AGENT_MONTHLY_CAP_MICRO_USD", "1")        # smaller than any worst-case estimate
    with pool.connection() as c:
        c.execute("TRUNCATE budget_buckets, inference_calls CASCADE")
    calls = []
    transport = httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))
    out = interpret(pool, RateCard.load(), "please send a hundred twenty bucks to aws for cloud stuff", recipients=["aws"],
                    categories=["cloud"], currency="USD", transport=transport, principal_id=uuid.uuid4())
    assert out["status"] == "unresolved" and out["reasons"] == ["AGENT_BUDGET_EXHAUSTED"] and out["proposal"] is None
    assert calls == []
    with pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM inference_calls").fetchone()["n"] == 0
