"""Evaluation runner. Run from the backend folder:

    cd backend && uv run python ../eval/runner.py --config offline        # A + gate + kernel (no API keys)
    cd backend && uv run python ../eval/runner.py --config A|B|C|gate|kernel [--split dev|heldout|all]

Configs (text cases):   A rules only | B rules + primary model | C rules + primary + escalation.
B and C call real models and are SKIPPED (not faked) when the API keys are absent.
Everything is measured from real executions against Postgres (schema BK_EVAL_SCHEMA, default bk_eval,
wiped at the start of every run). Metrics are never hard-coded; results are written to eval/results/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from budget_kernel import kernel
from budget_kernel.config import Settings
from budget_kernel.costledger.rate_card import RateCard
from budget_kernel.db.connection import make_pool
from budget_kernel.db.migrate import migrate
from budget_kernel.routing.agent import interpret_then_decide

ROOT = Path(__file__).resolve().parent
DATASET_VERSION = os.environ.get("BK_DATASET_VERSION", "v1")      # v2 = a fresh set nothing was tuned on
DATASET = ROOT / "datasets" / DATASET_VERSION / "cases.jsonl"
RECIPIENTS, CATEGORIES = ["aws", "google", "stripe", "github"], ["cloud", "ads", "payments", "tools"]
SC_ROOT = {"categories": ["cloud", "ads"], "recipients": ["aws", "google"], "per_tx_limit": 100_000, "can_delegate": True}
TEXT_SCOPE = {"categories": CATEGORIES, "recipients": RECIPIENTS, "per_tx_limit": 50_000, "can_delegate": True}
ERRORS = [(kernel.IdempotencyConflict, "IDEMPOTENCY_CONFLICT"), (kernel.DelegationRejected, "DELEGATION_REJECTED"),
          (kernel.Forbidden, "FORBIDDEN"), (kernel.Conflict, "CONFLICT"), (kernel.ValidationFailed, "VALIDATION_FAILED"),
          (kernel.NotFound, "NOT_FOUND"), (kernel.KernelBusy, "BUSY")]


def future(days=365):
    return datetime.now(timezone.utc) + timedelta(days=days)


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(q * len(s)))], 1)


# --------------------------------------------------------------------------- setup

class Env:
    def __init__(self):
        self.settings = Settings.load()
        self.schema = os.environ.get("BK_EVAL_SCHEMA", "bk_eval")
        migrate(self.settings, self.schema)
        self.pool = make_pool(self.settings, self.schema, max_size=10)
        with self.pool.connection() as c:
            c.execute("TRUNCATE principals, mandates, grants, transactions, ledger_movements, audit_events,"
                      " budget_buckets, inference_calls, chain_heads, grant_strikes CASCADE")
        self.owner, self.alice, self.bob, self.svc = (self._principal(n, k) for n, k in (
            ("owner", "human"), ("alice", "agent"), ("bob", "agent"), ("svc", "service")))
        self.card = RateCard.load()
        self.local = threading.local()

    def _principal(self, name, kind):
        with self.pool.connection() as c:
            return c.execute("INSERT INTO principals(name, kind) VALUES (%s,%s) RETURNING id", (name, kind)).fetchone()["id"]

    def reset_budget(self):
        with self.pool.connection() as c:
            c.execute("TRUNCATE budget_buckets, inference_calls CASCADE")

    def text_fixture(self):
        """One big grant per worker thread (each has its own mandate, so threads do not serialize)."""
        if not hasattr(self.local, "grant"):
            m = kernel.create_mandate(self.pool, owner_principal_id=self.owner, currency="USD", total=10**12,
                                      protected_reserve=0, expires_at=future(), scope=TEXT_SCOPE)
            g = kernel.delegate(self.pool, parent_grant_id=m["root_grant_id"], actor=self.owner,
                                holder_principal_id=self.alice, amount=10**11, expires_at=future(300),
                                scope=TEXT_SCOPE, idempotency_key=uuid.uuid4().hex)["grant_id"]
            self.local.grant = g
        return self.local.grant


def load_cases(kind, split):
    cases = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [c for c in cases if c["kind"] == kind and split in ("all", c["split"])]


# --------------------------------------------------------------------------- text cases

def decision_label(d):
    if d is None:
        return "none"
    if d["state"] == "rejected":
        return f"rejected:{d['reason']}"
    return {"reserved": "reserved", "proposed": "held"}.get(d["state"], d["state"])


def decision_ok(expected, got):
    return {"held_or_none": got in ("held", "none"), "not_reserved": got != "reserved"}.get(expected, got == expected)


def run_text_case(env, case, kwargs, run_id):
    exp = case["expect"]
    t0 = time.perf_counter()
    out = interpret_then_decide(
        env.pool, env.card, grant_id=env.text_fixture(), actor=env.alice, text=case["text"],
        idempotency_key=f"{run_id}-{case['id']}", recipients=RECIPIENTS, categories=CATEGORIES, currency="USD", **kwargs)
    latency = (time.perf_counter() - t0) * 1000
    interp, dec = out["interpretation"], out["decision"]
    trail = interp["trail"]
    steps = [s["step"] for s in trail]
    route = "fast_path" if steps[:1] == ["fast_path"] else ("model" if steps else "none")
    got_dec = decision_label(dec)
    if dec and dec["state"] == "reserved":      # keep the fixture grant funded
        kernel.release(env.pool, transaction_id=dec["transaction_id"], actor=env.alice)
    fields_ok = None
    if exp.get("fields") and interp["proposal"]:
        fields_ok = all(interp["proposal"].get(k) == v for k, v in exp["fields"].items())
    row = {
        "id": case["id"], "family": case["family"], "split": case["split"], "route": route, "status": interp["status"],
        "decision": got_dec, "latency_ms": latency, "reasons": interp["reasons"],
        "route_ok": exp["route"] in ("any", route), "status_ok": exp["status"] in ("any", interp["status"]),
        "decision_ok": decision_ok(exp["decision"], got_dec), "fields_ok": fields_ok,
        "model_calls": sum(1 for s in steps if s in ("primary", "escalation")), "escalated": "escalation" in steps,
    }
    exp_reserved = exp["decision"] == "reserved"
    row["unauthorized_approval"] = got_dec == "reserved" and not exp_reserved
    row["wrong_value_approval"] = got_dec == "reserved" and exp_reserved and fields_ok is False
    row["safe_miss"] = exp_reserved and got_dec != "reserved"
    row["correct"] = row["decision_ok"] and row["status_ok"] and fields_ok is not False
    return row


def summarize_text(rows, cost):
    n = len(rows)
    handled = [r for r in rows if r["model_calls"] or r["route"] == "fast_path"]
    calls = sum(r["model_calls"] for r in rows)
    model_rows = [r for r in rows if r["model_calls"]]
    correct = sum(r["correct"] for r in rows)
    fam = {}
    for r in rows:
        f = fam.setdefault(r["family"], {"n": 0, "correct": 0})
        f["n"] += 1
        f["correct"] += r["correct"]
    fcases = [r for r in rows if r["fields_ok"] is not None]
    return {
        "n": n, "correct": correct, "accuracy": round(correct / n, 4) if n else None,
        "decision_match": sum(r["decision_ok"] for r in rows), "status_match": sum(r["status_ok"] for r in rows),
        "route_match": sum(r["route_ok"] for r in rows),
        "field_exact_match": {"n": len(fcases), "ok": sum(1 for r in fcases if r["fields_ok"])},
        "unauthorized_approvals": sum(r["unauthorized_approval"] for r in rows),
        "wrong_value_approvals": sum(r["wrong_value_approval"] for r in rows),
        "safe_misses_failed_closed": sum(r["safe_miss"] for r in rows),
        "fast_path_share": round(sum(r["route"] == "fast_path" for r in rows) / n, 4) if n else None,
        "model_calls": calls, "escalation_rate_of_model_cases":
            round(sum(r["escalated"] for r in model_rows) / len(model_rows), 4) if model_rows else None,
        "latency_ms_p50": pct([r["latency_ms"] for r in rows], 0.5), "latency_ms_p95": pct([r["latency_ms"] for r in rows], 0.95),
        "inference": cost, "cost_micro_usd_per_correct": round(cost["actual_micro"] / correct, 2) if correct and cost["actual_micro"] else None,
        "by_family": {k: v for k, v in sorted(fam.items())},
        "failures": [{k: r[k] for k in ("id", "family", "status", "decision", "reasons")} for r in rows if not r["correct"]][:60],
    }


def inference_cost(env):
    with env.pool.connection() as c:
        r = c.execute("SELECT count(*) AS calls, coalesce(sum(actual_micro),0)::bigint AS actual_micro,"
                      " coalesce(sum(input_tokens),0)::bigint AS tokens_in, coalesce(sum(output_tokens),0)::bigint AS tokens_out,"
                      " coalesce(sum(overrun_micro),0)::bigint AS overrun_micro FROM inference_calls").fetchone()
    return dict(r)


def run_text(env, config, split):
    kwargs = {"A": {"allow_models": False}, "B": {"allow_escalation": False}, "C": {}}[config]
    cases = load_cases("text", split)
    env.reset_budget()
    run_id = uuid.uuid4().hex[:8]
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(lambda c: run_text_case(env, c, kwargs, run_id), cases))
    return summarize_text(rows, inference_cost(env))


# --------------------------------------------------------------------------- gate cases (recorded model outputs)

def scripted_transport(outputs):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        step = outputs[len(calls)] if len(calls) < len(outputs) else outputs[-1]
        calls.append(json.loads(request.content)["model"])
        if step == "TIMEOUT":
            raise httpx.ReadTimeout("scripted")
        if isinstance(step, str) and step.startswith("HTTP"):
            return httpx.Response(int(step[4:]), text="scripted")
        finish, usage = "stop", {"prompt_tokens": 120, "completion_tokens": 60}
        if isinstance(step, list) and step and step[0] == "TRUNC":
            finish, step = "length", step[1]
        text = step if isinstance(step, str) else json.dumps(step)
        return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": usage})
    return httpx.MockTransport(handler), calls


def run_gate(env, split):
    # Scripted transports never touch the network, but the adapter insists on a configured key.
    # Use throwaway values for this section only and restore whatever the environment really had.
    saved = {k: os.environ.get(k) for k in ("DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY")}
    os.environ["DASHSCOPE_API_KEY"] = os.environ["DEEPSEEK_API_KEY"] = "gate-scripted"
    try:
        return _run_gate(env, split)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run_gate(env, split):
    from budget_kernel.routing.interpret import interpret
    env.reset_budget()
    rows = []
    for c in load_cases("gate", split):
        transport, calls = scripted_transport(c["model_outputs"])
        out = interpret(env.pool, env.card, c["text"], recipients=RECIPIENTS, categories=CATEGORIES, currency="USD",
                        transport=transport)
        exp = c["expect"]
        escalated = any(s["step"] == "escalation" for s in out["trail"])
        ok_status = out["status"] == exp["status"]
        ok_esc = escalated == exp["escalated"]
        ok_reasons = all(r in out["reasons"] for r in exp["reasons_include"])
        rows.append({"id": c["id"], "family": c["family"], "split": c["split"], "ok": ok_status and ok_esc and ok_reasons,
                     "got": {"status": out["status"], "escalated": escalated, "reasons": out["reasons"]}, "expected": exp})
    return {"n": len(rows), "ok": sum(r["ok"] for r in rows),
            "note": "fixed recorded outputs: measures validation/escalation/fail-closed logic, NOT model quality",
            "failures": [r for r in rows if not r["ok"]]}


# --------------------------------------------------------------------------- kernel scripts

def kernel_label(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        for cls, label in ERRORS:
            if isinstance(exc, cls):
                return f"error:{label}"
        raise


def run_kernel_case(env, case):
    actors = {"owner": env.owner, "alice": env.alice, "bob": env.bob, "svc": env.svc}
    m = kernel.create_mandate(env.pool, owner_principal_id=env.owner, currency="USD", total=100_000,
                              protected_reserve=10_000, expires_at=future(), scope=SC_ROOT)
    # BK-303: a service principal may only run settlement steps on mandates it is bound to; the scripts model the
    # normal deployment, where the owner has bound the settlement service.
    kernel.bind_settler(env.pool, mandate_id=m["mandate_id"], actor=env.owner, principal_id=env.svc)
    grants, txs = {"root": m["root_grant_id"]}, {}
    expiry = {}
    with env.pool.connection() as c:
        expiry["root"] = c.execute("SELECT expires_at FROM grants WHERE id=%s", (m["root_grant_id"],)).fetchone()["expires_at"]
    results = []
    for i, st in enumerate(case["steps"]):
        op, who = st["op"], actors.get(st.get("actor", ""), None)
        P = env.pool

        def go():
            if op == "authorize":
                d = kernel.authorize(P, grant_id=grants[st["grant"]], actor=who, amount=st["amount"], currency=st["currency"],
                                     recipient=st["recipient"], category=st["category"],
                                     idempotency_key=st["key"] or f"k{i}-{uuid.uuid4().hex[:6]}", needs_review=st["needs_review"])
                if st.get("as"):
                    txs[st["as"]] = d["transaction_id"]
                return "reserved" if d["state"] == "reserved" else "proposed" if d["state"] == "proposed" else f"rejected:{d['reason']}"
            if op == "delegate":
                par = st["parent"]
                exp = expiry[par] if st["expires"] == "same" else datetime.now(timezone.utc) + timedelta(days=int(st["expires"][1:-1]))
                r = kernel.delegate(P, parent_grant_id=grants[par], actor=who, holder_principal_id=actors[st["holder"]],
                                    amount=st["amount"], expires_at=exp, scope=st["scope"],
                                    idempotency_key=st["key"] or f"d{i}-{uuid.uuid4().hex[:6]}")
                if st.get("as"):
                    grants[st["as"]] = r["grant_id"]
                    expiry[st["as"]] = exp
                return "ok"
            if op == "revoke":
                kernel.revoke(P, grant_id=grants[st["grant"]], actor=who); return "ok"
            if op == "release":
                kernel.release(P, transaction_id=txs[st["tx"]], actor=who); return "ok"
            if op == "settle":
                kernel.settle_start(P, transaction_id=txs[st["tx"]], actor=who)
                kernel.settle_confirm(P, transaction_id=txs[st["tx"]], actor=who); return "ok"
            if op == "settle_start":
                kernel.settle_start(P, transaction_id=txs[st["tx"]], actor=who); return "ok"
            if op == "settle_confirm":
                kernel.settle_confirm(P, transaction_id=txs[st["tx"]], actor=who); return "ok"
            if op == "settle_fail":
                kernel.settle_fail(P, transaction_id=txs[st["tx"]], actor=who, proof="eval"); return "ok"
            if op == "review":
                r = kernel.review(P, transaction_id=txs[st["tx"]], actor=who, approve=st["approve"])
                return "ok" if r["state"] == "reserved" else f"ok_rejected:{r['reason']}"
            if op == "create_mandate":
                kernel.create_mandate(P, owner_principal_id=who, currency="USD", total=1_000_000, protected_reserve=0,
                                      expires_at=future(), scope=SC_ROOT); return "ok"
            raise ValueError(op)

        got = kernel_label(go)
        viol = kernel.check_invariants(env.pool, m["mandate_id"])
        exp = st["expect"]
        results.append({"step": i, "op": op, "expected": exp, "got": got, "ok": got == exp,
                        "unauthorized": (exp.startswith(("rejected", "error")) and got in ("reserved", "ok", "proposed")),
                        "invariant_violations": viol})
    return {"id": case["id"], "family": case["family"], "split": case["split"], "steps": results,
            "ok": all(r["ok"] for r in results) and not any(r["invariant_violations"] for r in results)}


def run_kernel(env, split):
    cases = load_cases("kernel", split)
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(lambda c: run_kernel_case(env, c), cases))
    steps = [s for r in res for s in r["steps"]]
    return {"cases": len(res), "cases_ok": sum(r["ok"] for r in res), "steps": len(steps), "steps_ok": sum(s["ok"] for s in steps),
            "unauthorized_approvals": sum(s["unauthorized"] for s in steps),
            "invariant_violations": sum(len(s["invariant_violations"]) for s in steps),
            "note": "invariants I1,I2,I3,I5 checked after every step; a zero result is scoped to these scripts only",
            "failures": [{"id": r["id"], "family": r["family"],
                          "steps": [s for s in r["steps"] if not s["ok"] or s["invariant_violations"]]} for r in res if not r["ok"]]}


# --------------------------------------------------------------------------- main

def missing_keys(config: str) -> list[str]:
    """Config B uses the primary model only; C also escalates, so it needs the second provider's key too."""
    need = {"B": ["DASHSCOPE_API_KEY"], "C": ["DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"]}[config]
    return [k for k in need if not os.environ.get(k, "").strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="offline", choices=["offline", "A", "B", "C", "gate", "kernel"])
    ap.add_argument("--split", default="all", choices=["all", "dev", "heldout"])
    args = ap.parse_args()
    wanted = {"offline": ["A", "gate", "kernel"]}.get(args.config, [args.config])
    env = Env()
    report = {"dataset": json.loads((ROOT / "datasets" / DATASET_VERSION / "MANIFEST.json").read_text()),
              "started_at": datetime.now(timezone.utc).isoformat(), "split": args.split, "sections": {},
              "git_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                           cwd=ROOT).stdout.strip(), "rate_card_version": env.card.version}
    # keep a real env var from leaking into offline-only gate runs: scripted transports never use the network
    for name in wanted:
        t0 = time.perf_counter()
        if name in ("B", "C") and missing_keys(name):
            report["sections"][f"text_{name}"] = {"skipped": "model API keys not configured; no numbers were invented"}
            print(f"[{name}] SKIPPED: set {' and '.join(missing_keys(name))} in .env")
            continue
        if name in ("A", "B", "C"):
            report["sections"][f"text_{name}"] = run_text(env, name, args.split)
        elif name == "gate":
            report["sections"]["gate"] = run_gate(env, args.split)
        else:
            report["sections"]["kernel"] = run_kernel(env, args.split)
        print(f"[{name}] done in {time.perf_counter() - t0:.0f}s")
    out_dir = ROOT / "results" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.config}-{args.split}-{datetime.now(timezone.utc).strftime('%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("failures", "by_family")} for k, v in report["sections"].items()},
                     indent=2, default=str))
    print("results:", path)
    env.pool.close()


if __name__ == "__main__":
    main()
