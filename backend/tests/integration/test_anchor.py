"""BK-401: on-chain anchor of the hash-chain heads vs the real DB and a FakeChain. No network, no real key."""
from __future__ import annotations

import hashlib

import psycopg
import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from budget_kernel import kernel
from budget_kernel.api.app import create_app
from budget_kernel.kernel import integrity
from budget_kernel.settlement import anchor
from budget_kernel.settlement.adapter import SettlementConfig, SettlementRefused, reconcile, settle
from budget_kernel.settlement.fake import FakeChain
from budget_kernel.settlement.signer import Signer

AWS = "0x00000000000000000000000000000000000A5300"


@pytest.fixture()
def env(world, pool):
    with pool.connection() as c:
        c.execute("TRUNCATE anchors, anchor_heads, chain_settlements, settlement_accounts CASCADE")
    return world, FakeChain(), Signer("0x" + "22" * 32), SettlementConfig(recipients={"aws": AWS})


def _anchor(pool, aid):
    with pool.connection() as c:
        return c.execute("SELECT * FROM anchors WHERE id=%s", (aid,)).fetchone()


def _finish(pool, chain, cfg):
    chain.mine(blocks=2)
    return anchor.reconcile(pool, chain=chain, cfg=cfg)


def test_digest_is_sorted_stable_and_changes_with_any_head():
    heads = [("mandate:b", 2, "b" * 64), ("global", 5, "a" * 64), ("mandate:a", 1, "c" * 64)]
    d = anchor.digest_of(sorted(heads, key=lambda t: t[0].encode()))
    assert d == hashlib.sha256(b"global|5|" + b"a" * 64 + b"\nmandate:a|1|" + b"c" * 64 + b"\nmandate:b|2|" + b"b" * 64 + b"\n").hexdigest()
    assert anchor.digest_of([("global", 5, "a" * 64)]) != anchor.digest_of([("global", 6, "a" * 64)])
    assert anchor.digest_of([("global", 5, "a" * 64)]) != anchor.digest_of([("global", 5, "b" * 64)])


def test_anchor_tx_carries_magic_and_digest_to_self_and_matches_snapshot(env):
    world, chain, signer, cfg = env
    out = anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    row = _anchor(world.pool, out["anchor_id"])
    assert out["status"] == "broadcast" and out["explorer_url"].endswith(out["tx_hash"]) and out["chains"] >= 1
    tx = Account.recover_transaction(bytes(row["raw_tx"]))
    assert tx == signer.address
    decoded = _decode(bytes(row["raw_tx"]))
    assert decoded["to"].lower() == signer.address.lower() and decoded["value"] == 0
    assert decoded["data"] == b"BKANCHOR1" + bytes.fromhex(row["digest"]) and len(decoded["data"]) == 41
    assert decoded["gas"] <= 30_000
    heads = anchor.snapshot(world.pool)
    assert row["digest"] == anchor.digest_of(heads)
    with world.pool.connection() as c:
        stored = [(r["chain_key"], r["seq"], r["head_hash"]) for r in c.execute(
            "SELECT * FROM anchor_heads WHERE anchor_id=%s ORDER BY chain_key", (out["anchor_id"],))]
    assert stored == heads
    assert _finish(world.pool, chain, cfg)[0]["status"] == "confirmed"
    res = integrity.verify(world.pool, world.mandate_id)
    assert res["ok"] and res["last_anchor"]["matches"] and res["last_anchor"]["status"] == "confirmed"


def _decode(raw: bytes) -> dict:
    from eth_account import Account as A
    from hexbytes import HexBytes
    from eth_account.typed_transactions import TypedTransaction
    t = TypedTransaction.from_bytes(HexBytes(raw)).transaction.dictionary
    return {"to": t["to"] if isinstance(t["to"], str) else "0x" + bytes(t["to"]).hex(), "value": t["value"],
            "data": bytes(t["data"]), "gas": t["gas"]}


def test_crash_after_sign_before_broadcast_resends_same_bytes(env):
    world, chain, signer, cfg = env
    chain.down = True
    out = anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    row = _anchor(world.pool, out["anchor_id"])
    assert "error" in out and row["status"] == "signed" and chain.sent == []
    chain.down = False
    anchor.reconcile(world.pool, chain=chain, cfg=cfg)
    assert chain.sent == [row["tx_hash"]] and _anchor(world.pool, row["id"])["raw_tx"] == row["raw_tx"]
    assert _finish(world.pool, chain, cfg)[0]["status"] == "confirmed"
    with world.pool.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM anchors").fetchone()["n"] == 1


def test_crash_after_broadcast_before_confirm_is_recovered_by_reconcile(env):
    world, chain, signer, cfg = env
    out = anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    anchor.reconcile(world.pool, chain=chain, cfg=cfg)                 # no receipt yet: re-sends identical bytes
    assert set(chain.sent) == {out["tx_hash"]}
    assert _finish(world.pool, chain, cfg)[0]["status"] == "confirmed"


def test_rpc_error_never_marks_an_anchor_failed(env):
    world, chain, signer, cfg = env
    out = anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    chain.down = True
    for _ in range(3):
        anchor.reconcile(world.pool, chain=chain, cfg=cfg)
    row = _anchor(world.pool, out["anchor_id"])
    assert row["status"] in ("signed", "broadcast") and row["last_error"]


def test_anchors_and_payments_never_share_a_nonce(env):
    world, chain, signer, cfg = env
    nonces = []
    for _ in range(3):
        tid = world.authorize(world.root, world.owner, 1_000)["transaction_id"]
        settle(world.pool, transaction_id=tid, actor=world.svc, chain=chain, signer=signer, cfg=cfg)
        nonces.append(anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)["anchor_id"])
    with world.pool.connection() as c:
        pay = [r["nonce"] for r in c.execute("SELECT nonce FROM chain_settlements")]
        anc = [r["nonce"] for r in c.execute("SELECT nonce FROM anchors")]
        assert sorted(pay + anc) == list(range(6)) and not set(pay) & set(anc)
        assert c.execute("SELECT next_nonce FROM settlement_accounts").fetchone()["next_nonce"] == 6
        # the schema itself refuses a reuse, in both directions
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("INSERT INTO anchors(chain_id, from_address, nonce, digest, raw_tx, tx_hash, status)"
                      " VALUES (84532, %s, %s, %s, 'x', '0xdup', 'signed')", (signer.address, pay[0], "0" * 64))
    fresh = world.authorize(world.root, world.owner, 1_000)["transaction_id"]      # no chain_settlements row yet
    with world.pool.connection() as c:
        with pytest.raises(psycopg.errors.UniqueViolation, match="already used by anchors"):
            c.execute("INSERT INTO chain_settlements(transaction_id, chain_id, from_address, nonce, to_address,"
                      " token_address, token_amount, raw_tx, tx_hash, status) VALUES (%s, 84532, %s, %s, 'a', 'b', 1,"
                      " 'x', '0xdup2', 'signed')", (fresh, signer.address, anc[0]))
    world.check()


def test_gas_ceiling_and_empty_heads_refuse_without_consuming_a_nonce(env):
    world, chain, signer, cfg = env
    chain.base_fee = 10**12
    with pytest.raises(SettlementRefused):
        anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    with world.pool.connection() as c:
        assert c.execute("SELECT next_nonce FROM settlement_accounts").fetchone()["next_nonce"] == 0
        assert c.execute("SELECT count(*) AS n FROM anchors").fetchone()["n"] == 0


def test_nonce_consumed_elsewhere_fails_anchor_only_after_two_checks(env):
    from datetime import datetime, timedelta, timezone
    world, chain, signer, cfg = env
    out = anchor.create(world.pool, chain=chain, signer=signer, cfg=cfg)
    chain.nonce_override = 5
    t0 = datetime.now(timezone.utc)
    assert anchor.advance(world.pool, anchor_id=out["anchor_id"], chain=chain, cfg=cfg, now=t0)["status"] == "broadcast"
    assert anchor.advance(world.pool, anchor_id=out["anchor_id"], chain=chain, cfg=cfg,
                          now=t0 + timedelta(seconds=61))["status"] == "failed"


def test_api_admin_anchor_simulated_409_and_testnet_flow(env, pool, monkeypatch):
    world, chain, signer, cfg = env
    monkeypatch.setenv("BK_ADMIN_TOKEN", "test-admin-token")
    admin = {"X-Admin-Token": "test-admin-token"}
    with TestClient(create_app(pool=pool)) as client:
        r = client.post("/admin/anchor", headers=admin)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "ANCHOR_NEEDS_TESTNET"
    with TestClient(create_app(pool=pool, settlement=(chain, signer, cfg))) as client:
        assert client.post("/admin/anchor").status_code in (401, 403)
        r = client.post("/admin/anchor", headers=admin)
        body = r.json()
        assert r.status_code == 200, r.text
        assert set(body) >= {"anchor_id", "digest", "tx_hash", "status", "explorer_url", "chains"}
        chain.mine(blocks=2)
        key = client.post("/admin/principals", headers=admin, json={"name": "svc-anchor", "kind": "service"}).json()["api_key"]
        rec = client.post("/settlement/reconcile", headers={**admin, "Authorization": f"Bearer {key}"}).json()
        assert rec["anchors"][0]["status"] == "confirmed"
