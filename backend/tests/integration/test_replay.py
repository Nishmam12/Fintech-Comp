"""BK-305 (closes R9): /agent/request looks up the idempotency key BEFORE interpreting. A retry makes zero model calls."""
import uuid

from tests.integration.test_agent_flow import ask, env, make_client, person, setup  # noqa: F401  (env is autouse)
from tests.integration.test_interpret import QWEN, Fake, proposal

MESSY = "Please settle the AWS invoice for $120.50 for cloud hosting"


def test_retry_makes_zero_model_calls_and_replays_the_same_decision(pool):
    fake = Fake(**{QWEN: [proposal(amount=12050)]})
    with make_client(pool, fake) as client:
        _, agent, _, g = setup(client)
        first = ask(client, agent, g, MESSY, key="k-retry").json()
        assert fake.calls == [QWEN] and first["decision"]["replayed"] is False
        again = ask(client, agent, g, MESSY, key="k-retry")
        assert again.status_code == 200 and fake.calls == [QWEN]         # no second model call
        body = again.json()
        assert body["decision"]["transaction_id"] == first["decision"]["transaction_id"]
        assert (body["decision"]["state"], body["decision"]["reason"]) == (first["decision"]["state"], None)
        assert body["decision"]["replayed"] is True and body["interpretation"]["replayed"] is True
        assert body["interpretation"]["proposal"]["amount_minor"] == 12050
        assert "request_text_sha256" not in body["interpretation"]["proposal"]


def test_replay_of_a_rejection_is_identical_and_adds_no_second_transaction(pool):
    fake = Fake()
    with make_client(pool, fake) as client:
        owner, agent, mid, g = setup(client)
        r1 = ask(client, agent, g, "Pay $300.00 to AWS for cloud", key="k-rej").json()    # fast path, over per-tx limit
        r2 = ask(client, agent, g, "Pay $300.00 to AWS for cloud", key="k-rej").json()
        assert r1["decision"]["reason"] == r2["decision"]["reason"] == "PER_TX_LIMIT_EXCEEDED"
        assert r2["decision"]["transaction_id"] == r1["decision"]["transaction_id"] and r2["decision"]["replayed"]
        txs = client.get(f"/mandates/{mid}/state", headers=owner).json()["transactions"]
        assert len(txs) == 1
        assert fake.calls == []


def test_changed_text_under_the_same_key_is_a_conflict_and_never_reinterpreted(pool):
    fake = Fake(**{QWEN: [proposal(amount=12050)]})
    with make_client(pool, fake) as client:
        _, agent, _, g = setup(client)
        ask(client, agent, g, MESSY, key="k-chg")
        r = ask(client, agent, g, MESSY + " please", key="k-chg")
        assert r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_CONFLICT"
        assert fake.calls == [QWEN]                                      # still only the first call


def test_non_holder_gets_403_and_learns_nothing_about_the_stored_decision(pool):
    fake = Fake(**{QWEN: [proposal(amount=12050)]})
    with make_client(pool, fake) as client:
        owner, agent, _, g = setup(client)
        ask(client, agent, g, MESSY, key="k-nh")
        _, stranger = person(client, "stranger")
        for who in (stranger, owner):
            r = ask(client, who, g, MESSY, key="k-nh")
            assert r.status_code in (403,) and "transaction_id" not in r.text
        assert fake.calls == [QWEN]


def test_owner_cannot_trigger_a_model_call_on_someone_elses_grant(pool):
    fake = Fake()
    with make_client(pool, fake) as client:
        owner, _, _, g = setup(client)
        r = ask(client, owner, g, MESSY, key=uuid.uuid4().hex)
        assert r.status_code == 403 and r.json()["code"] == "NOT_GRANT_HOLDER" and fake.calls == []
