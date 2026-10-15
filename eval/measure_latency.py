"""Measure what one kernel operation costs, with and without the ADR-0008 controls.

    uv run --project ../backend python measure_latency.py [--n 25]

Runs in the evaluation schema (bk_eval) against the real database, sequentially (no contention), and
writes eval/results/<date>/latency-<time>.json. Numbers include the ~60 ms round trip to the hosted DB.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from budget_kernel import kernel  # noqa: E402
from budget_kernel.config import Settings  # noqa: E402
from budget_kernel.db.connection import make_pool  # noqa: E402
from budget_kernel.db.migrate import migrate  # noqa: E402

SCHEMA = "bk_eval"
BASE = {"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 1_000, "can_delegate": True}


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(ms):
    return {"n": len(ms), "median_ms": round(statistics.median(ms)), "p95_ms": round(pct(ms, 0.95)),
            "min_ms": round(min(ms)), "max_ms": round(max(ms))}


def main(n: int) -> None:
    import time
    st = Settings.load()
    migrate(st, SCHEMA)
    pool = make_pool(st, SCHEMA, max_size=4)

    def principal(name, kind):
        with pool.connection() as c:
            return c.execute("INSERT INTO principals(name, kind) VALUES (%s,%s) RETURNING id", (name, kind)).fetchone()["id"]

    owner, agent = principal("latency-owner", "human"), principal("latency-agent", "agent")
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    total = 1_000 * n * 2 + 10_000
    m = kernel.create_mandate(pool, owner_principal_id=owner, currency="USD", total=total, protected_reserve=0,
                              expires_at=expires, scope={**BASE, "per_tx_limit": total})

    def grant(**extra):
        return kernel.delegate(pool, parent_grant_id=m["root_grant_id"], actor=owner, holder_principal_id=agent,
                               amount=1_000 * n, expires_at=expires, scope={**BASE, **extra},
                               idempotency_key=uuid.uuid4().hex)["grant_id"]

    plain = grant()
    guarded = grant(window_limit=10_000_000, window_seconds=3600, review_above=500_000)   # controls on, never triggered

    out = {}
    for label, g in (("plain_grant", plain), ("with_window_and_threshold", guarded)):
        ms = []
        for _ in range(n):
            t0 = time.perf_counter()
            d = kernel.authorize(pool, grant_id=g, actor=agent, amount=1_000 // 10, currency="USD", recipient="aws",
                                 category="cloud", idempotency_key=uuid.uuid4().hex)
            ms.append((time.perf_counter() - t0) * 1000)
            assert d["state"] == "reserved", d
        out[label] = summarize(ms)
    assert kernel.check_invariants(pool, m["mandate_id"]) == []
    out["delta_median_ms"] = out["with_window_and_threshold"]["median_ms"] - out["plain_grant"]["median_ms"]
    out["note"] = ("Sequential authorizations on the hosted database, including network round trips. The guarded grant "
                   "has a window and a threshold set but neither triggers; delta is the added cost of evaluating them.")
    when = datetime.now(timezone.utc)
    dest = Path(__file__).resolve().parent / "results" / when.strftime("%Y-%m-%d")
    dest.mkdir(parents=True, exist_ok=True)
    f = dest / f"latency-{when.strftime('%H%M%S')}.json"
    f.write_text(json.dumps({"measured_at": when.isoformat(), "schema": SCHEMA, **out}, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("saved", f)
    pool.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    main(ap.parse_args().n)
