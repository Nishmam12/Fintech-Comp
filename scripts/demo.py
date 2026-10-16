"""Clean-start demo replay against a running API (no model keys needed).

    uv run --project backend uvicorn budget_kernel.api.app:app --port 8000     # terminal 1
    uv run --project backend python scripts/demo.py [--attacks]                # terminal 2

Reads BK_ADMIN_TOKEN from the environment or .env. Creates fresh principals and a fresh mandate on
every run, so it can be replayed any number of times. API keys are never printed.
Exit code 0 only if every expectation below held.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PAY = os.environ.get("DEMO_PAY_USD", "50")   # whole USD paid in beat 6; a real testnet run sets this tiny (wallet holds ~20 test USDC)


def _admin_token() -> str:
    if os.environ.get("BK_ADMIN_TOKEN"):
        return os.environ["BK_ADMIN_TOKEN"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("BK_ADMIN_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("BK_ADMIN_TOKEN is not set (environment or .env)")


class Demo:
    def __init__(self, base: str):
        self.http = httpx.Client(base_url=base, timeout=120)
        self.admin = {"X-Admin-Token": _admin_token()}
        self.failures: list[str] = []

    def say(self, msg: str) -> None:
        print(msg, flush=True)

    def expect(self, label: str, ok: bool, detail: str = "") -> None:
        self.say(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
        if not ok:
            self.failures.append(label)

    def principal(self, name: str, kind: str) -> tuple[str, dict]:
        r = self.http.post("/admin/principals", json={"name": name, "kind": kind}, headers=self.admin)
        r.raise_for_status()
        j = r.json()
        return j["principal_id"], {"Authorization": f"Bearer {j['api_key']}"}

    def post(self, path: str, headers: dict, body: dict | None = None) -> httpx.Response:
        return self.http.post(path, json=body or {}, headers=headers)

    def run(self, attacks: bool) -> int:
        tag = uuid.uuid4().hex[:6]
        self.say("== 1. Health")
        self.expect("API reachable", self.http.get("/health").json().get("ok") is True)

        self.say("== 2. People: a human owner, an AI agent, a settlement service")
        owner_id, owner = self.principal(f"demo-owner-{tag}", "human")
        agent_id, agent = self.principal(f"demo-agent-{tag}", "agent")
        svc_id, svc = self.principal(f"demo-settler-{tag}", "service")

        self.say("== 3. Owner creates a mandate: 1000.00 USD, 100.00 protected (never spendable)")
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)
        scope = {"categories": ["cloud", "software"], "recipients": ["aws", "github"], "per_tx_limit": 20_000,
                 "can_delegate": True}
        r = self.post("/mandates", owner, {"currency": "USD", "total": 100_000, "protected_reserve": 10_000,
                                           "expires_at": expires.isoformat(), "scope": scope})
        m = r.json()
        self.expect("mandate created", r.status_code == 201, f"spendable {m.get('available')}")
        mandate, root = m["mandate_id"], m["root_grant_id"]

        self.say("== 4. An agent cannot mint its own authority")
        r = self.post("/mandates", agent, {"currency": "USD", "total": 100_000, "protected_reserve": 0,
                                           "expires_at": expires.isoformat(), "scope": scope})
        self.expect("agent-created mandate refused", r.status_code == 403, r.json().get("code", ""))

        self.say("== 5. Owner delegates 300.00 to the agent: narrower scope, cannot re-delegate")
        child_scope = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 10_000, "can_delegate": False}
        r = self.post("/grants", owner, {"parent_grant_id": root, "holder_principal_id": agent_id, "amount": 30_000,
                                         "expires_at": expires.isoformat(), "scope": child_scope,
                                         "idempotency_key": f"d-{tag}"})
        self.expect("delegation created", r.status_code == 201)
        grant = r.json()["grant_id"]
        r = self.post("/grants", owner, {"parent_grant_id": root, "holder_principal_id": agent_id, "amount": 30_000,
                                         "expires_at": expires.isoformat(),
                                         "scope": {**child_scope, "categories": ["cloud", "payroll"]},
                                         "idempotency_key": f"d2-{tag}"})
        self.expect("wider scope than the parent is refused", r.status_code >= 400, r.json().get("code", ""))

        def ask(text: str, key: str, gid: str | None = None) -> dict:
            return self.post("/agent/request", agent, {"grant_id": gid or grant, "text": text, "idempotency_key": key}).json()

        self.say("== 6. The agent asks in plain language; the kernel decides")
        d = ask(f"pay {PAY} USD to aws for cloud", f"r1-{tag}")
        decision = d["decision"] or {}
        self.expect("in-scope request reserved", decision.get("state") == "reserved",
                    f"route={[t['step'] for t in d['interpretation']['trail']]}")
        tx = decision.get("transaction_id")
        d = ask("pay 150 USD to aws for cloud", f"r2-{tag}")
        self.expect("over the per-transaction limit rejected", (d["decision"] or {}).get("reason") == "PER_TX_LIMIT_EXCEEDED")
        r = self.post("/transactions/authorize", agent, {"grant_id": grant, "amount": 2_000, "currency": "USD",
                                                          "recipient": "github", "category": "cloud",
                                                          "idempotency_key": f"r3-{tag}"})
        self.expect("recipient outside the grant rejected", r.json().get("reason") == "RECIPIENT_NOT_ALLOWED")
        again = ask(f"pay {PAY} USD to aws for cloud", f"r1-{tag}")
        self.expect("retry with the same key replays, no double reservation",
                    (again["decision"] or {}).get("replayed") is True
                    and again["decision"]["transaction_id"] == tx)

        self.say("== 7. Settlement (simulated; real Base Sepolia transfer when the API runs with BK_SETTLEMENT_MODE=testnet)")
        self.post(f"/mandates/{mandate}/settlers", owner, {"principal_id": svc_id})     # BK-303: owner binds the service
        r = self.post(f"/transactions/{tx}/settle", svc)
        j = r.json()
        if "tx_hash" in j:                                    # BK_SETTLEMENT_MODE=testnet: a real Base Sepolia transfer
            self.say(f"  broadcast {j['tx_hash']}\n  explorer  {j['explorer_url']}")
            for _ in range(40):                               # reconcile until 2 confirmations (~2 s blocks)
                time.sleep(3)
                res = self.http.post("/settlement/reconcile", headers={**svc, **self.admin}).json().get("results", [])
                if any(x["tx_hash"] == j["tx_hash"] and x["status"] in ("confirmed", "failed") for x in res):
                    break
            st = next(t for t in self.http.get(f"/mandates/{mandate}/state", headers=owner).json()["transactions"] if t["id"] == tx)
            self.expect("real testnet transfer confirmed and settled", st["chain_status"] == "confirmed" and st["state"] == "settled",
                        f"block {st['block_number']}")
        else:
            self.expect("settlement service settles the reservation", j.get("state") == "settled")
        r = self.post(f"/transactions/{tx}/settle-fail", owner, {"proof": "owner-claims-failure"})
        self.expect("owner cannot declare a settled transfer failed", r.status_code >= 400, r.json().get("code", ""))

        self.say("== 7b. Guard rails: approval threshold and velocity window (a second 200.00 grant)")
        guarded = {**child_scope, "window_limit": 15_000, "window_seconds": 3600, "review_above": 6_000}
        r = self.post("/grants", owner, {"parent_grant_id": root, "holder_principal_id": agent_id, "amount": 20_000,
                                         "expires_at": expires.isoformat(), "scope": guarded,
                                         "idempotency_key": f"d3-{tag}"})
        self.expect("guarded grant created (review above 60.00, at most 150.00 per hour)", r.status_code == 201)
        g2 = r.json()["grant_id"]
        d = ask("pay 70 USD to aws for cloud", f"g1-{tag}", g2)
        held = d["decision"] or {}
        self.expect("a 70.00 request is held for the owner, nothing reserved",
                    held.get("state") == "proposed" and held.get("review_reason") == "ABOVE_THRESHOLD")
        r = self.post(f"/transactions/{held['transaction_id']}/review", owner, {"approve": True})
        self.expect("owner approves it and the money is reserved", r.json().get("state") == "reserved")
        d = ask("pay 50 USD to aws for cloud", f"g2-{tag}", g2)
        self.expect("a 50.00 request is under the threshold and reserved", (d["decision"] or {}).get("state") == "reserved")
        d = ask("pay 40 USD to aws for cloud", f"g3-{tag}", g2)
        self.expect("the next 40.00 would break the hourly limit and is refused",
                    (d["decision"] or {}).get("reason") == "VELOCITY_LIMIT_EXCEEDED")
        st = self.http.get(f"/mandates/{mandate}/state", headers=owner).json()
        used = next(x for x in st["grants"] if x["id"] == g2).get("window_used")
        self.expect("the server reports window use (120.00 of 150.00)", used == 12_000, f"window_used={used}")

        self.say("== 7c. Circuit breaker: an agent that keeps probing its limits is suspended (a third 100.00 grant)")
        r = self.post("/grants", owner, {"parent_grant_id": root, "holder_principal_id": agent_id, "amount": 10_000,
                                         "expires_at": expires.isoformat(), "scope": child_scope,
                                         "idempotency_key": f"d4-{tag}"})
        g3 = r.json()["grant_id"]
        last = {}
        for i in range(5):
            last = self.post("/transactions/authorize", agent, {"grant_id": g3, "amount": 1_000, "currency": "USD",
                                                                "recipient": "aws", "category": "gambling",
                                                                "idempotency_key": f"p{i}-{tag}"}).json()
        self.expect("five probes outside the grant's categories are each refused",
                    last.get("reason") == "CATEGORY_NOT_ALLOWED")
        self.expect("the fifth refusal suspends the grant", last.get("suspended") is True)
        r = self.post("/transactions/authorize", agent, {"grant_id": g3, "amount": 1_000, "currency": "USD",
                                                          "recipient": "aws", "category": "cloud",
                                                          "idempotency_key": f"p6-{tag}"})
        self.expect("even a valid request is now refused", r.json().get("reason") == "GRANT_SUSPENDED")
        r = self.post(f"/grants/{g3}/reinstate", agent)
        self.expect("the agent cannot reinstate itself", r.status_code == 403, r.json().get("code", ""))
        r = self.post(f"/grants/{g3}/reinstate", owner)
        self.expect("the owner reinstates it", r.json().get("status") == "active")
        r = self.post("/transactions/authorize", agent, {"grant_id": g3, "amount": 1_000, "currency": "USD",
                                                          "recipient": "aws", "category": "cloud",
                                                          "idempotency_key": f"p7-{tag}"})
        self.expect("a valid request is served again", r.json().get("state") == "reserved")

        self.say("== 8. Owner revokes the agent's grant; the agent is cut off immediately")
        r = self.post(f"/grants/{grant}/revoke", owner)
        self.expect("revoked", r.json().get("status") == "revoked")
        d = ask("pay 10 USD to aws for cloud", f"r4-{tag}")
        self.expect("agent request after revocation rejected", (d["decision"] or {}).get("reason") == "GRANT_REVOKED")

        self.say("== 9. Ledger invariants")
        st = self.http.get(f"/mandates/{mandate}/state", headers=owner).json()
        self.expect("conservation and backing invariants hold", st["invariants"]["ok"], str(st["invariants"]["violations"]))
        ig = self.http.get(f"/mandates/{mandate}/integrity", headers=owner).json()
        self.expect("the hash-chained history verifies", ig.get("ok") is True,
                    f"{ig.get('length')} rows, head {str(ig.get('head_hash'))[:12]}")
        ev = self.http.get(f"/mandates/{mandate}/audit", headers=owner).json()["events"]
        self.say(f"  audit trail: {len(ev)} events, e.g. {', '.join(sorted({e['kind'] for e in ev})[:6])}")

        if attacks:
            self.say("== 10. Attack scenarios: unsafe baseline vs kernel (measured, each takes a while)")
            names = self.http.get("/simulation/scenarios", headers=owner).json()["scenarios"]
            for name in names:
                res = self.post("/simulation/run", owner, {"scenario": name}).json()
                if "kernel" not in res:
                    self.expect(f"{name} ran", False, str(res))
                    continue
                self.say(f"  {name}:\n      baseline: {res['naive']['summary']}\n      kernel:   {res['kernel']['summary']}")
                self.expect(f"{name}: kernel held", res["kernel"]["violated"] is False)

        self.say("\nRESULT: " + ("all expectations held" if not self.failures else f"{len(self.failures)} FAILED: {self.failures}"))
        return 0 if not self.failures else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BK_API_URL", "http://localhost:8000"))
    ap.add_argument("--attacks", action="store_true", help="also run the baseline-vs-kernel attack scenarios")
    a = ap.parse_args()
    sys.exit(Demo(a.base_url).run(a.attacks))
