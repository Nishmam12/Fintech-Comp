"""Named attack scenarios (competition demo + security evidence).

Each scenario runs the same attack twice: against the intentionally unsafe baseline and against the
deterministic kernel, on real Postgres, and returns MEASURED outcomes. Nothing here is canned: a
scenario that cannot reproduce its violation reports violated=False for the baseline too.

This is the only package allowed to import budget_kernel.naive_baseline.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from budget_kernel import kernel
from budget_kernel.naive_baseline import ops as naive

OWNER_SCOPE = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 100_000, "can_delegate": True}
FUTURE = lambda: datetime.now(timezone.utc) + timedelta(days=30)  # noqa: E731


# ------------------------------------------------------------------ helpers

def _principal(pool, name: str, kind: str):
    """Keyless principals: simulation identities cannot be used through the public API."""
    with pool.connection() as c:
        row = c.execute("SELECT id FROM principals WHERE name = %s AND kind = %s AND api_key_hash IS NULL",
                        (name, kind)).fetchone()
        if row:
            return row["id"]
        return c.execute("INSERT INTO principals(name, kind) VALUES (%s,%s) RETURNING id", (name, kind)).fetchone()["id"]


def _retry(fn, attempts: int = 12):
    """Clients retry a retryable 'busy' answer (ADR-0005); the count is reported, never hidden."""
    busy = 0
    for i in range(attempts):
        try:
            return fn(), busy
        except kernel.KernelBusy:
            busy += 1
            time.sleep(0.15 * (i + 1))
    raise kernel.KernelBusy("gave up after retries")


def _gave_up(res) -> int:
    """Attempts that ended in an exception (e.g. still busy after every retry). Reported separately:
    refusing everything would look 'safe', so liveness must be visible next to safety."""
    return sum(1 for r in res if not isinstance(r, tuple))


def _race(fns):
    barrier = threading.Barrier(len(fns))

    def run(fn):
        barrier.wait()
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - reported to the caller as a failed attempt
            return exc

    with ThreadPoolExecutor(max_workers=len(fns)) as ex:
        return [f.result() for f in [ex.submit(run, fn) for fn in fns]]


class Fixture:
    """A fresh mandate: 100_000 total, 10_000 protected, so 90_000 spendable."""

    def __init__(self, pool):
        self.pool = pool
        tag = uuid.uuid4().hex[:6]
        self.owner = _principal(pool, "simulation-owner", "human")
        self.agent = _principal(pool, "simulation-agent", "agent")
        self.agent2 = _principal(pool, "simulation-agent-2", "agent")
        self.svc = _principal(pool, "simulation-settler", "service")
        m = kernel.create_mandate(pool, owner_principal_id=self.owner, currency="USD", total=100_000,
                                  protected_reserve=10_000, expires_at=FUTURE(), scope=OWNER_SCOPE)
        self.mandate, self.root, self.tag = m["mandate_id"], m["root_grant_id"], tag
        kernel.bind_settler(pool, mandate_id=self.mandate, actor=self.owner, principal_id=self.svc)

    def delegate(self, parent, holder, amount, actor=None):
        # A child may not outlive its parent: inherit the parent's own expiry.
        return kernel.delegate(self.pool, parent_grant_id=parent, actor=actor or self.owner, holder_principal_id=holder,
                               amount=amount, expires_at=self.grant(parent)["expires_at"], scope=OWNER_SCOPE,
                               idempotency_key=uuid.uuid4().hex)["grant_id"]

    def authorize(self, grant, actor, amount, key=None):
        return kernel.authorize(self.pool, grant_id=grant, actor=actor, amount=amount, currency="USD", recipient="aws",
                                category="cloud", idempotency_key=key or uuid.uuid4().hex)

    def invariants(self):
        return kernel.check_invariants(self.pool, self.mandate)

    def grant(self, gid):
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM grants WHERE id = %s", (gid,)).fetchone()


def _result(name, title, proves, naive_out, kernel_out, informational=False):
    return {"scenario": name, "title": title, "what_it_proves": proves, "informational": informational,
            "naive": naive_out, "kernel": kernel_out}


# ------------------------------------------------------------------ scenarios

def concurrency_overspend(pool, n: int = 8, amount: int = 30_000, funds: int = 90_000) -> dict:
    run = naive.new_run()
    w = naive.create_wallet(pool, run, funds)
    oks = _race([lambda: naive.spend(pool, run, w, amount) for _ in range(n)])
    t = naive.totals(pool, run)
    naive_out = {"violated": t["spent_total"] > funds,
                 "metrics": {"requests": n, "approved": sum(1 for o in oks if o is True), "funds": funds, **t},
                 "summary": f"approved {sum(1 for o in oks if o is True)} of {n} requests; spent {t['spent_total']} from {funds}"}
    fx = Fixture(pool)
    res = _race([lambda: _retry(lambda: fx.authorize(fx.root, fx.owner, amount)) for _ in range(n)])
    decisions = [r[0] for r in res if isinstance(r, tuple)]
    reserved = sum(1 for d in decisions if d["state"] == "reserved")
    inv = fx.invariants()
    kernel_out = {"violated": reserved * amount > funds or bool(inv),
                  "metrics": {"requests": n, "approved": reserved, "reserved_total": reserved * amount, "funds": funds,
                              "busy_retries": sum(r[1] for r in res if isinstance(r, tuple)), "gave_up": _gave_up(res),
                              "invariant_violations": inv},
                  "summary": f"approved {reserved} of {n}; reserved {reserved * amount} of {funds}; "
                             f"gave up {_gave_up(res)}; invariants hold: {not inv}"}
    return _result("concurrency_overspend", "Concurrent overspend",
                   "Parallel spend requests cannot exceed the funds that exist", naive_out, kernel_out)


def delegation_amplification(pool, n: int = 6, amount: int = 30_000, funds: int = 90_000) -> dict:
    run = naive.new_run()
    parent = naive.create_wallet(pool, run, funds)
    kids = _race([lambda: naive.delegate(pool, run, parent, amount) for _ in range(n)])
    made = [k for k in kids if k is not None and not isinstance(k, Exception)]
    naive_out = {"violated": len(made) * amount > funds,
                 "metrics": {"children_created": len(made), "delegated_total": len(made) * amount, "parent_funds": funds},
                 "summary": f"created {len(made)} children holding {len(made) * amount} from a parent with {funds}"}
    fx = Fixture(pool)
    res = _race([lambda: _retry(lambda: fx.delegate(fx.root, fx.agent, amount)) for _ in range(n)])
    ok = [r for r in res if isinstance(r, tuple)]
    refused = sum(1 for r in res if isinstance(r, kernel.DelegationRejected))
    inv = fx.invariants()
    kernel_out = {"violated": len(ok) * amount > funds or bool(inv),
                  "metrics": {"children_created": len(ok), "delegated_total": len(ok) * amount, "parent_funds": funds,
                              "rejected": refused, "gave_up": n - len(ok) - refused, "invariant_violations": inv},
                  "summary": f"created {len(ok)} children holding {len(ok) * amount} of {funds}; invariants hold: {not inv}"}
    return _result("delegation_amplification", "Delegation amplification",
                   "Delegating transfers authority; it can never create more than the parent holds", naive_out, kernel_out)


def revoked_ancestor(pool) -> dict:
    run = naive.new_run()
    root = naive.create_wallet(pool, run, 90_000)
    child = naive.delegate(pool, run, root, 30_000)
    grandchild = naive.delegate(pool, run, child, 10_000)
    naive.revoke(pool, child)
    approved = naive.spend(pool, run, grandchild, 1_000)
    naive_out = {"violated": bool(approved), "metrics": {"grandchild_spend_after_ancestor_revoked": bool(approved)},
                 "summary": "grandchild still spent after its parent was revoked" if approved else "spend refused"}
    fx = Fixture(pool)
    c = fx.delegate(fx.root, fx.agent, 30_000)
    g = fx.delegate(c, fx.agent2, 10_000, actor=fx.agent)
    kernel.revoke(pool, grant_id=c, actor=fx.owner)
    d = fx.authorize(g, fx.agent2, 1_000)
    inv = fx.invariants()
    kernel_out = {"violated": d["state"] == "reserved" or bool(inv),
                  "metrics": {"decision": d["state"], "reason": d["reason"], "descendant_status": fx.grant(g)["status"],
                              "invariant_violations": inv},
                  "summary": f"grandchild {d['state']} ({d['reason']}); descendant status {fx.grant(g)['status']}"}
    return _result("revoked_ancestor", "Revoked ancestor",
                   "Revoking a grant invalidates all of its descendants for new spending", naive_out, kernel_out)


def revocation_race(pool, n: int = 6, amount: int = 5_000) -> dict:
    """Revoke while spends are in flight. Outcome in the baseline is timing-dependent (reported as measured)."""
    run = naive.new_run()
    root = naive.create_wallet(pool, run, 90_000)
    child = naive.delegate(pool, run, root, 30_000)
    revoked_at = {}

    def do_revoke():
        naive.revoke(pool, child)
        with pool.connection() as c:
            revoked_at["t"] = c.execute("SELECT clock_timestamp() AS t").fetchone()["t"]

    _race([do_revoke] + [lambda: naive.spend(pool, run, child, amount) for _ in range(n)])
    with pool.connection() as c:
        late = c.execute("SELECT count(*) AS n FROM naive_spends WHERE run_id = %s AND created_at > %s",
                         (run, revoked_at["t"] - timedelta(seconds=0))).fetchone()["n"]
    naive_out = {"violated": late > 0, "metrics": {"spends_recorded_after_revoke_committed": late},
                 "summary": f"{late} spend(s) were recorded after the revocation committed (timing-dependent)"}
    fx = Fixture(pool)
    c = fx.delegate(fx.root, fx.agent, 30_000)
    res = _race([lambda: _retry(lambda: kernel.revoke(pool, grant_id=c, actor=fx.owner))]
                + [lambda: _retry(lambda: fx.authorize(c, fx.agent, amount)) for _ in range(n)])
    with pool.connection() as cn:
        live = cn.execute("SELECT count(*) AS n FROM transactions WHERE grant_id = %s AND state IN ('reserved','submitted')",
                          (c,)).fetchone()["n"]
    inv = fx.invariants()
    g = fx.grant(c)
    kernel_out = {"violated": live > 0 or bool(inv) or g["reserved"] != 0,
                  "metrics": {"live_reservations_on_revoked_grant": live, "grant_status": g["status"],
                              "grant_available": g["available"], "gave_up": _gave_up(res), "invariant_violations": inv},
                  "summary": f"{live} live reservation(s) on the revoked grant; invariants hold: {not inv}"}
    return _result("revocation_race", "Revocation race",
                   "Whatever order revoke and spend interleave in, no live authority survives revocation",
                   naive_out, kernel_out)


def replay_duplicate(pool, n: int = 5, amount: int = 10_000) -> dict:
    run = naive.new_run()
    w = naive.create_wallet(pool, run, 90_000)
    key = uuid.uuid4().hex
    _race([lambda: naive.spend(pool, run, w, amount, key) for _ in range(n)])
    t = naive.totals(pool, run)
    naive_out = {"violated": t["spend_count"] > 1,
                 "metrics": {"requests_with_same_key": n, "debits": t["spend_count"], "spent_total": t["spent_total"]},
                 "summary": f"the same request sent {n} times was debited {t['spend_count']} times"}
    fx = Fixture(pool)
    key = uuid.uuid4().hex
    res = _race([lambda: _retry(lambda: fx.authorize(fx.root, fx.owner, amount, key)) for _ in range(n)])
    ids = {r[0]["transaction_id"] for r in res if isinstance(r, tuple)}
    g = fx.grant(fx.root)
    inv = fx.invariants()
    kernel_out = {"violated": len(ids) != 1 or g["reserved"] != amount or bool(inv),
                  "metrics": {"requests_with_same_key": n, "transactions_created": len(ids), "reserved": g["reserved"],
                              "gave_up": _gave_up(res), "invariant_violations": inv},
                  "summary": f"the same request sent {n} times created {len(ids)} transaction; reserved {g['reserved']}"}
    return _result("replay_duplicate", "Replay / duplicate delivery",
                   "An idempotency key bound to the payload makes retries safe", naive_out, kernel_out)


def split_purchases(pool, per_tx: int = 10_000, grant_funds: int = 50_000, window_limit: int = 20_000) -> dict:
    """Splitting defeats a per-transaction limit (the grant balance still bounds it). A velocity window
    (ADR-0008) is the control that stops it; both grants are attacked identically and measured."""
    fx = Fixture(pool)
    expires = FUTURE() - timedelta(minutes=1)

    def grant(funds, **extra):
        return kernel.delegate(pool, parent_grant_id=fx.root, actor=fx.owner, holder_principal_id=fx.agent,
                               amount=funds, expires_at=expires, scope={**OWNER_SCOPE, "per_tx_limit": per_tx, **extra},
                               idempotency_key=uuid.uuid4().hex)["grant_id"]

    plain = grant(grant_funds)
    big = fx.authorize(plain, fx.agent, 30_000)
    parts = [fx.authorize(plain, fx.agent, per_tx) for _ in range(7)]
    approved = sum(1 for p in parts if p["state"] == "reserved")
    windowed = grant(grant_funds - 10_000, window_limit=window_limit, window_seconds=3600)
    wparts = [fx.authorize(windowed, fx.agent, per_tx) for _ in range(7)]
    wapproved = sum(1 for p in wparts if p["state"] == "reserved")
    wrefusal = next((p["reason"] for p in wparts if p["state"] == "rejected"), None)
    inv = fx.invariants()
    note = (f"The per-transaction limit is not a velocity limit: a 30,000 request is refused, but {approved} "
            f"requests of {per_tx} are approved. Total spend is still capped by the grant's balance. A grant with "
            f"a velocity window of {window_limit} per hour refuses the same split after {wapproved} ({wrefusal}).")
    kernel_out = {"violated": bool(inv) or wapproved * per_tx > window_limit, "informational_finding": True,
                  "metrics": {"single_large_request": big["reason"], "split_requests_approved": approved,
                              "split_total": approved * per_tx, "grant_funds": grant_funds,
                              "windowed_requests_approved": wapproved, "windowed_total": wapproved * per_tx,
                              "window_limit": window_limit, "windowed_refusal": wrefusal, "invariant_violations": inv},
                  "summary": f"one {30_000} request: {big['reason']}; {approved} split requests of {per_tx} approved "
                             f"(total {approved * per_tx} of {grant_funds}) -- {note}"}
    return _result("split_purchases", "Split purchases (per-tx limit vs velocity window)",
                   "A per-transaction cap can be split; a velocity window over the grant subtree stops the split",
                   {"violated": None, "metrics": {}, "summary": "not applicable: baseline has no per-transaction limit"},
                   kernel_out, informational=True)


SCENARIOS = {
    "concurrency_overspend": concurrency_overspend,
    "delegation_amplification": delegation_amplification,
    "revoked_ancestor": revoked_ancestor,
    "revocation_race": revocation_race,
    "replay_duplicate": replay_duplicate,
    "split_purchases": split_purchases,
}


_RUNNING = threading.Lock()


def run(pool, name: str) -> dict:
    """One simulation at a time per process: a scenario uses up to 8 pooled connections, and
    overlapping runs would starve real API requests on the same pool."""
    if name not in SCENARIOS:
        raise KeyError(name)
    if not _RUNNING.acquire(blocking=False):
        raise kernel.Conflict("a simulation is already running", code="SIMULATION_RUNNING")
    try:
        t0 = time.perf_counter()
        out = SCENARIOS[name](pool)
        out["duration_ms"] = round((time.perf_counter() - t0) * 1000)
        return out
    finally:
        _RUNNING.release()
