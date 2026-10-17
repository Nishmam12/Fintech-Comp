"""Background housekeeping (BK-403). Authorizes nothing: every pass only runs things that already exist and
are safe to repeat (settlement/anchor reconcile, cost-ledger stale sweep, the kernel sweep for due mandates).
Runs as a thread inside the API process when BK_WORKER=1; BK_WORKER_INTERVAL seconds between passes (default 30).
Payment reconcile acts as the service principal BK_WORKER_PRINCIPAL, which the mandate owners must have bound
as a settler (unbinding it stops the worker for that mandate)."""
from __future__ import annotations

import logging
import os
import threading
import uuid

from budget_kernel import kernel
from budget_kernel.costledger import ledger as cost_ledger

log = logging.getLogger("budget_kernel.worker")


def run_once(pool, *, settlement=None, actor=None) -> dict:
    """One pass. Each step is isolated: a failure is logged (type only, never a message that could hold a raw
    transaction) and the next step still runs."""
    out: dict = {}

    def step(name, fn):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001 - the loop must survive anything
            out[name] = f"error:{type(e).__name__}"
            log.warning("worker step %s failed: %s", name, type(e).__name__)

    if settlement is not None:
        chain, _, cfg = settlement
        from budget_kernel.settlement import anchor
        from budget_kernel.settlement.adapter import reconcile
        if actor is not None:
            step("reconcile", lambda: len(reconcile(pool, actor=actor, chain=chain, cfg=cfg)))
        step("anchors", lambda: len(anchor.reconcile(pool, chain=chain, cfg=cfg)))
    step("cost_sweep", lambda: cost_ledger.sweep_stale(pool))
    failures = 0

    def ticks():
        nonlocal failures
        done = 0
        for m in kernel.due_mandates(pool):
            try:                                  # one busy or failing mandate must not make the rest wait a full interval
                kernel.tick(pool, m)
                done += 1
            except Exception as e:  # noqa: BLE001
                failures += 1
                log.warning("worker tick failed: %s", type(e).__name__)
        return done

    step("ticks", ticks)
    if failures:
        out["tick_failures"] = failures
    return out


class Worker:
    def __init__(self, pool, *, settlement=None, interval: float | None = None):
        p = os.environ.get("BK_WORKER_PRINCIPAL")
        self.pool, self.settlement = pool, settlement
        self.actor = uuid.UUID(p) if p else None
        self.interval = interval if interval is not None else float(os.environ.get("BK_WORKER_INTERVAL", "30"))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="bk-worker", daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            run_once(self.pool, settlement=self.settlement, actor=self.actor)
            self._stop.wait(self.interval)

    def start(self) -> "Worker":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)
