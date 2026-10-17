"""BK-402: unbinding a settlement service."""
from __future__ import annotations

import pytest

from budget_kernel import kernel
from tests.conftest import new_principal


def test_only_owner_can_unbind_and_it_is_idempotent(world):
    with pytest.raises(kernel.Forbidden) as e:
        kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.alice, principal_id=world.svc)
    assert e.value.code == "NOT_OWNER"
    with pytest.raises(kernel.Forbidden):
        kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.svc, principal_id=world.svc)
    out = kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    assert out["already"] is False and world.audit_kinds().count("SETTLER_UNBOUND") == 1
    again = kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    assert again["already"] is True and world.audit_kinds().count("SETTLER_UNBOUND") == 1
    world.check()


def test_unbound_service_gets_not_settler_on_every_step(world):
    tid = world.authorize(world.root, world.owner, 1_000)["transaction_id"]
    sub = world.authorize(world.root, world.owner, 1_000)["transaction_id"]
    kernel.settle_start(world.pool, transaction_id=sub, actor=world.svc)
    kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    for call in (lambda: kernel.settle_start(world.pool, transaction_id=tid, actor=world.svc),
                 lambda: kernel.settle_confirm(world.pool, transaction_id=sub, actor=world.svc),
                 lambda: kernel.settle_fail(world.pool, transaction_id=sub, actor=world.svc, proof="x")):
        with pytest.raises(kernel.Forbidden) as e:
            call()
        assert e.value.code == "NOT_SETTLER"
    world.check()


def test_in_flight_transfer_survives_unbind(world):
    a = world.authorize(world.root, world.owner, 1_000)["transaction_id"]
    b = world.authorize(world.root, world.owner, 2_000)["transaction_id"]
    for t in (a, b):
        kernel.settle_start(world.pool, transaction_id=t, actor=world.svc)
    kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    assert world.tx(a)["state"] == "submitted" and world.tx(b)["state"] == "submitted"
    kernel.settle_confirm(world.pool, transaction_id=a, actor=world.owner)            # the owner can still finish it
    assert world.tx(a)["state"] == "settled"
    world.check()
    kernel.bind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    kernel.settle_confirm(world.pool, transaction_id=b, actor=world.svc)               # re-binding lets the service finish
    assert world.tx(b)["state"] == "settled"
    world.check()


def test_unbind_other_mandates_binding_untouched(world):
    other = new_principal(world.pool, "owner2", "human")
    m2 = kernel.create_mandate(world.pool, owner_principal_id=other, currency="USD", total=1_000, protected_reserve=0,
                               expires_at=world.grant(world.root)["expires_at"], scope={"categories": ["cloud"], "recipients": ["aws"], "per_tx_limit": 1_000, "can_delegate": False})
    kernel.bind_settler(world.pool, mandate_id=m2["mandate_id"], actor=other, principal_id=world.svc)
    kernel.unbind_settler(world.pool, mandate_id=world.mandate_id, actor=world.owner, principal_id=world.svc)
    with world.pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM mandate_settlers WHERE mandate_id=%s", (m2["mandate_id"],)).fetchone()["n"] == 1


def test_delete_endpoint_owner_only(world, pool):
    from fastapi.testclient import TestClient
    from budget_kernel.api.app import create_app
    from budget_kernel.api.auth import hash_key
    keys = {}
    with pool.connection() as c:
        for who in ("owner", "alice"):
            keys[who] = f"k-{who}-{world.mandate_id}"
            c.execute("UPDATE principals SET api_key_hash=%s WHERE id=%s", (hash_key(keys[who]), getattr(world, who)))
    h = lambda w: {"Authorization": f"Bearer {keys[w]}"}
    url = f"/mandates/{world.mandate_id}/settlers/{world.svc}"
    with TestClient(create_app(pool=pool)) as client:
        assert client.delete(url, headers=h("alice")).status_code == 403
        assert client.delete(url, headers=h("owner")).json()["already"] is False
        assert client.delete(url, headers=h("owner")).json()["already"] is True
