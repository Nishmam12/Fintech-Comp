"""Inference cost ledger (ADR-0006 'Evidence and validation') against real Postgres."""
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from budget_kernel.costledger import ledger
from budget_kernel.costledger.rate_card import (Rate, RateCard, RouteUnavailable, actual_cost,
                                                estimate_worst_case)

RATE = Rate("testprov", "test-model", price_in=1_000_000, price_cached=100_000, price_out=2_000_000,
            reasoning_billing="as_output", fixed_fee=0, version="test-v1")
SMALL = {"global": 1_000, "primary": 600, "escalation": 800, "retries": 300, "eval": 200}


_used: set = set()


@pytest.fixture()
def month():
    """A distinct far-future month per test, so tests never share budget rows."""
    while True:
        m = date(random.randrange(2200, 9000), random.randrange(1, 13), 1)
        if m not in _used:
            _used.add(m)
            return m


def buckets(pool, m):
    with pool.connection() as c:
        return {r["bucket"]: r for r in c.execute("SELECT * FROM budget_buckets WHERE month = %s", (m,))}


def test_reserve_then_reconcile_charges_actual(pool, month):
    call = ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=SMALL)
    out = ledger.reconcile(pool, call["id"], {"input_tokens": 20, "output_tokens": 10})
    assert (out["status"], out["actual_micro"]) == ("reconciled", 40)       # 20*1 + 10*2 micro
    b = buckets(pool, month)
    for name in ("global", "primary"):
        assert (b[name]["reserved_micro"], b[name]["spent_micro"]) == (0, 40)
    assert ledger.reconcile(pool, call["id"], {"input_tokens": 1, "output_tokens": 1})["actual_micro"] == 40  # idempotent


def test_fifty_concurrent_reservations_never_overshoot_global(pool, month):
    caps = {**SMALL, "primary": 5_000}            # global (1_000) is the binding cap: exactly 10 x 100 fit
    barrier = threading.Barrier(20)

    def attempt(_):
        if _ < 20:
            barrier.wait()
        try:
            ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=caps)
            return True
        except ledger.BudgetExhausted:
            return False

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(attempt, range(50)))
    assert results.count(True) == 10
    b = buckets(pool, month)
    assert b["global"]["reserved_micro"] == 1_000 <= b["global"]["cap_micro_usd"]


def test_route_cap_binds_before_global(pool, month):
    ok = 0
    for _ in range(10):
        try:
            ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=SMALL)
            ok += 1
        except ledger.BudgetExhausted:
            pass
    assert ok == 6                                      # primary cap 600
    assert buckets(pool, month)["global"]["reserved_micro"] == 600


def test_overrun_is_charged_to_global_and_retries_and_audited(pool, month):
    call = ledger.reserve(pool, route="primary", rate=RATE, est_micro=50, month=month, caps=SMALL)
    out = ledger.reconcile(pool, call["id"], {"input_tokens": 30, "output_tokens": 20})  # actual 70
    assert (out["actual_micro"], out["overrun_micro"]) == (70, 20)
    b = buckets(pool, month)
    assert (b["primary"]["spent_micro"], b["global"]["spent_micro"], b["retries"]["spent_micro"]) == (50, 70, 20)
    with pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM audit_events WHERE kind = 'COST_OVERRUN' AND subject_id = %s",
                         (call["id"],)).fetchone()["n"] == 1


def test_missing_or_garbage_usage_is_charged_worst_case(pool, month):
    for usage in (None, {"output_tokens": 3}, {"input_tokens": -1, "output_tokens": 1}):
        call = ledger.reserve(pool, route="eval", rate=RATE, est_micro=30, month=month, caps=SMALL)
        out = ledger.reconcile(pool, call["id"], usage)
        assert (out["status"], out["actual_micro"]) == ("charged_worst_case", 30)
    assert buckets(pool, month)["eval"]["spent_micro"] == 90


def test_release_before_generation_frees_the_reservation(pool, month):
    call = ledger.reserve(pool, route="escalation", rate=RATE, est_micro=200, month=month, caps=SMALL)
    assert ledger.release(pool, call["id"])["status"] == "released"
    b = buckets(pool, month)
    assert (b["escalation"]["reserved_micro"], b["escalation"]["spent_micro"]) == (0, 0)


def test_charge_lands_in_the_month_of_reservation(pool, month):
    """A call reserved at the end of one month and reconciled later is charged to its own month."""
    call = ledger.reserve(pool, route="primary", rate=RATE, est_micro=100, month=month, caps=SMALL)
    later = date(month.year + 1, month.month, 1)
    ledger.reserve(pool, route="primary", rate=RATE, est_micro=1, month=later, caps=SMALL)  # "next month" exists
    ledger.reconcile(pool, call["id"], {"input_tokens": 10, "output_tokens": 5})
    assert buckets(pool, month)["primary"]["spent_micro"] == 20
    assert buckets(pool, later)["primary"]["spent_micro"] == 0


def test_stale_calls_are_charged_worst_case_not_released(pool, month):
    call = ledger.reserve(pool, route="primary", rate=RATE, est_micro=80, month=month, caps=SMALL)
    with pool.connection() as c:
        c.execute("UPDATE inference_calls SET created_at = clock_timestamp() - interval '11 minutes' WHERE id = %s",
                  (call["id"],))
    assert ledger.sweep_stale(pool) >= 1
    with pool.connection() as c:
        row = c.execute("SELECT status, actual_micro FROM inference_calls WHERE id = %s", (call["id"],)).fetchone()
    assert (row["status"], row["actual_micro"]) == ("charged_worst_case", 80)
    assert buckets(pool, month)["primary"]["spent_micro"] == 80


def test_mixed_route_concurrency_has_no_deadlocks(pool, month):
    caps = {"global": 10**9, "primary": 10**9, "escalation": 10**9, "retries": 10**9, "eval": 10**9}

    def work(i):
        route = ("primary", "escalation", "eval", "retries")[i % 4]
        call = ledger.reserve(pool, route=route, rate=RATE, est_micro=10 + i, month=month, caps=caps)
        usage = {"input_tokens": 5, "output_tokens": 10 + i}           # some calls overrun -> lock 'retries'
        return ledger.reconcile(pool, call["id"], usage)["status"]

    with ThreadPoolExecutor(max_workers=10) as ex:
        statuses = list(ex.map(work, range(60)))
    assert statuses == ["reconciled"] * 60
    b = buckets(pool, month)
    assert all(r["reserved_micro"] == 0 for r in b.values())
    assert b["global"]["spent_micro"] == sum(5 + 2 * (10 + i) for i in range(60))


# ----------------------------------------------------------------- rate card (no database)

def test_estimate_is_integer_and_rounds_up():
    assert estimate_worst_case(RATE, prompt_bytes=1, max_tokens=1) == 3       # ceil(1)+ceil(2)
    assert estimate_worst_case(RATE, prompt_bytes=1_000, max_tokens=500) == 2_000


def test_reasoning_tokens_billed_separately_when_declared():
    prices = {"price_in_micro_per_mtok": 1_000_000, "price_cached_micro_per_mtok": 0,
              "price_out_micro_per_mtok": 1_000_000, "fixed_fee_micro": 0, "reasoning_billing": "separate"}
    usage = {"input_tokens": 10, "output_tokens": 10, "reasoning_tokens": 30}
    assert actual_cost(prices, usage) == 50
    assert actual_cost({**prices, "reasoning_billing": "as_output"}, usage) == 20


def test_unknown_or_unverified_models_are_unavailable(tmp_path):
    entry = {"provider": "p", "model_id": "m", "region": "intl", "input_price_micro_per_Mtok": 1,
             "cached_input_price_micro_per_Mtok": 1, "output_price_micro_per_Mtok": 1, "reasoning_billing": "none",
             "fixed_fee_micro": 0, "source_url": "https://example.invalid", "accessed_on": "2026-10-15"}
    path = tmp_path / "card.json"
    path.write_text(json.dumps({"version": "t", "models": [{**entry, "verified": False},
                                                           {**entry, "model_id": "ok", "verified": True},
                                                           {**entry, "model_id": "float", "verified": True,
                                                            "output_price_micro_per_Mtok": 0.5}]}))
    card = RateCard.load(path)
    assert card.rate("p", "ok").price_in == 1
    for model in ("m", "float", "nope"):
        with pytest.raises(RouteUnavailable):
            card.rate("p", model)


def test_committed_rate_card_is_valid_and_enforces_price_tier():
    card = RateCard.load()
    qwen = card.rate("dashscope", "qwen3.7-flash-2026-07-15")
    assert card.rate("deepseek", "deepseek-flash").price_out == 1_200_000
    assert estimate_worst_case(qwen, prompt_bytes=3_000, max_tokens=400) == 142
    with pytest.raises(RouteUnavailable):                       # would bill at the 32K+ tier
        estimate_worst_case(qwen, prompt_bytes=40_000, max_tokens=400)
