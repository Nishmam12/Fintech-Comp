"""Property-based state machine (ADR-0004 evidence): random op sequences, invariants after every step.

Each generated example builds a fresh mandate and applies a random sequence of delegate /
authorize / settle-start / settle-confirm / settle-fail / release / revoke. Expected business
refusals (Conflict, DelegationRejected) are fine; anything else (assertion inside the kernel,
DB constraint violation, Forbidden for a legitimate actor) fails the test, as does any
violation of I1-I3.
"""
import uuid

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, invariant, rule, run_state_machine_as_test

from budget_kernel import kernel
from tests.conftest import future, new_principal, scope

EXPECTED = (kernel.Conflict, kernel.DelegationRejected)
CATEGORIES = st.sampled_from(["cloud", "ads", "gambling"])
RECIPIENTS = st.sampled_from(["aws", "google", "evil-corp"])


class KernelMachine(RuleBasedStateMachine):
    pool = None  # injected by the test below
    grants = Bundle("grants")
    txs = Bundle("txs")

    def __init__(self):
        super().__init__()
        p = self.pool
        self.owner = new_principal(p, "owner", "human")
        self.agents = [new_principal(p, f"agent{i}") for i in range(3)]
        self.svc = new_principal(p, "settler", "service")
        m = kernel.create_mandate(p, owner_principal_id=self.owner, currency="USD", total=100_000,
                                  protected_reserve=10_000, expires_at=future(30), scope=scope(per_tx_limit=60_000))
        self.mandate_id = m["mandate_id"]
        self.holder = {m["root_grant_id"]: self.owner}
        self.root = m["root_grant_id"]

    def _expires(self, gid):
        with self.pool.connection() as c:
            return c.execute("SELECT expires_at FROM grants WHERE id = %s", (gid,)).fetchone()["expires_at"]

    @rule(target=grants)
    def root_grant(self):
        return self.root

    @rule(target=grants, parent=grants, amount=st.integers(1, 40_000), agent=st.integers(0, 2),
          can_delegate=st.booleans(), narrow=st.booleans(),
          window=st.sampled_from([None, (15_000, 3600), (30_000, 3600), (30_000, 600)]),
          threshold=st.sampled_from([None, 0, 5_000, 12_000]))
    def delegate(self, parent, amount, agent, can_delegate, narrow, window, threshold):
        holder = self.agents[agent]
        sc = scope(per_tx_limit=20_000, can_delegate=can_delegate,
                   **({"categories": ["cloud"], "recipients": ["aws"]} if narrow else {}))
        if window:                                    # ADR-0008 controls, some of which delegation must refuse
            sc.update(window_limit=window[0], window_seconds=window[1])
        if threshold is not None:
            sc["review_above"] = threshold
        try:
            gid = kernel.delegate(self.pool, parent_grant_id=parent, actor=self.holder[parent], holder_principal_id=holder,
                                  amount=amount, expires_at=self._expires(parent), scope=sc,
                                  idempotency_key=uuid.uuid4().hex)["grant_id"]
        except EXPECTED:
            return parent  # keep the bundle non-empty without inventing a grant
        self.holder[gid] = holder
        return gid

    @rule(target=txs, grant=grants, amount=st.integers(1, 70_000), category=CATEGORIES, recipient=RECIPIENTS)
    def authorize(self, grant, amount, category, recipient):
        d = kernel.authorize(self.pool, grant_id=grant, actor=self.holder[grant], amount=amount, currency="USD",
                             recipient=recipient, category=category, idempotency_key=uuid.uuid4().hex)
        assert d["state"] in ("reserved", "rejected", "proposed")
        return d["transaction_id"]

    @rule(tx=txs, approve=st.booleans())
    def review(self, tx, approve):
        kernel.review(self.pool, transaction_id=tx, actor=self.owner, approve=approve)

    @rule(tx=txs)
    def settle_start(self, tx):
        try:
            kernel.settle_start(self.pool, actor=self.owner, transaction_id=tx)
        except EXPECTED:
            pass

    @rule(tx=txs)
    def settle_confirm(self, tx):
        try:
            kernel.settle_confirm(self.pool, actor=self.owner, transaction_id=tx)
        except EXPECTED:
            pass

    @rule(tx=txs)
    def settle_fail(self, tx):
        try:
            kernel.settle_fail(self.pool, actor=self.svc, transaction_id=tx, proof="receipt status 0 (simulated)")
        except EXPECTED:
            pass

    @rule(tx=txs)
    def release(self, tx):
        try:
            kernel.release(self.pool, transaction_id=tx, actor=self.owner)
        except EXPECTED:
            pass

    @rule(grant=consumes(grants))
    def revoke(self, grant):
        if grant == self.root:
            return  # root revocation freezes everything; covered by a dedicated test
        kernel.revoke(self.pool, grant_id=grant, actor=self.owner)

    @invariant()
    def accounting_holds(self):
        if self.pool is not None and hasattr(self, "mandate_id"):
            assert kernel.check_invariants(self.pool, self.mandate_id) == []


@pytest.mark.slow
@pytest.mark.timeout(1800)
def test_random_operation_sequences_preserve_invariants(pool):
    KernelMachine.pool = pool
    run_state_machine_as_test(
        KernelMachine,
        settings=settings(max_examples=12, stateful_step_count=14, deadline=None,
                          suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]),
    )
