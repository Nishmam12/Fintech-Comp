"""HTTP API. Thin layer: authenticate, parse strictly, call the kernel, map errors.

The API never decides anything about money; every decision comes from budget_kernel.kernel.
    uv run uvicorn budget_kernel.api.app:app --reload
"""
from __future__ import annotations

import hmac
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from budget_kernel import kernel, simulation
from budget_kernel.kernel import breaker, integrity
from budget_kernel.kernel.tx import audit as write_audit
from budget_kernel.proposals.validate import injection_suspected
from budget_kernel.costledger import ledger as cost_ledger
from budget_kernel.costledger.rate_card import RateCard
from budget_kernel.routing.agent import interpret_then_decide, stored_replay
from budget_kernel.routing.interpret import interpret as run_interpret
from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool

from . import schemas
from .auth import Caller, Principal, current_principal, hash_key, new_key, require_admin
from .ratelimit import RateLimiter


EXPLORER = os.environ.get("BK_EXPLORER_URL") or "https://sepolia-explorer.base.org/tx/"   # tx-page prefix; one source for state + adapter


def _uuid(v: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(v))
    except ValueError:
        raise HTTPException(422, {"code": f"BAD_{what.upper()}_ID", "message": f"{what} id is not a UUID"}) from None


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _settlement_from_env():
    """None in the default 'simulated' mode. In 'testnet' mode: RPC chain, signer from .env, operator recipient registry."""
    if os.environ.get("BK_SETTLEMENT_MODE", "simulated") != "testnet":
        return None
    import json
    from budget_kernel.settlement.adapter import SettlementConfig
    from budget_kernel.settlement.chain import RpcChain
    from budget_kernel.settlement.signer import Signer
    cfg = SettlementConfig(recipients=json.load(open(os.environ["BK_SETTLEMENT_RECIPIENTS"])), explorer=EXPLORER)
    chain = RpcChain(os.environ.get("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org"), cfg.chain_id)
    return chain, Signer(os.environ["SETTLEMENT_PRIVATE_KEY"]), cfg


def create_app(pool=None, schema: str | None = None, card: RateCard | None = None, llm_transport=None,
               settlement=None, ratelimit: RateLimiter | None = None) -> FastAPI:
    """settlement: (chain, signer, cfg) injected by tests; otherwise built from env when BK_SETTLEMENT_MODE=testnet."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = pool is None
        if owned:
            st = Settings.load()
            app.state.pool = make_pool(st, schema or st.schema)
        else:
            app.state.pool = pool
        app.state.card = card or RateCard.load()
        app.state.llm_transport = llm_transport      # tests inject a mock HTTP transport; None in production
        app.state.settlement = settlement or _settlement_from_env()
        yield
        if owned:
            app.state.pool.close()

    app = FastAPI(title="Budget Kernel", version="0.1.0", lifespan=lifespan)
    limiter = RateLimiter() if ratelimit is None else ratelimit             # per process (ADR-0009 C1); added first so CORS wraps its 429s
    app.state.ratelimit = limiter
    app.middleware("http")(limiter.middleware)
    # The dashboard (Next.js dev server) calls this API from the browser. Origins are an explicit allowlist.
    origins = [o.strip() for o in os.environ.get("BK_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type", "X-Admin-Token"])

    @app.exception_handler(kernel.KernelError)
    async def kernel_error(_: Request, exc: kernel.KernelError):
        return JSONResponse(status_code=exc.http_status, content={"code": exc.code, "message": str(exc)})

    def P(request: Request):
        return request.app.state.pool

    # ------------------------------------------------------------- admin / bootstrap

    @app.post("/admin/principals", dependencies=[Depends(require_admin)], status_code=201)
    def create_principal(body: schemas.CreatePrincipal, request: Request):
        raw = new_key()
        with P(request).connection() as c:
            row = c.execute("INSERT INTO principals(name, kind, api_key_hash, key_expires_at)"
                            " VALUES (%s,%s,%s, CASE WHEN %s::int IS NULL THEN NULL"
                            "   ELSE clock_timestamp() + make_interval(days => %s::int) END)"
                            " RETURNING id, key_expires_at",
                            (body.name, body.kind, hash_key(raw), body.expires_in_days, body.expires_in_days)).fetchone()
        return _jsonable({"principal_id": str(row["id"]), "api_key": raw, "key_expires_at": row["key_expires_at"],
                          "note": "store this key now; it is not shown again"})

    @app.post("/admin/principals/{principal_id}/disable", dependencies=[Depends(require_admin)])
    def disable_principal(principal_id: str, request: Request):
        """Stop a principal from authenticating. Idempotent. It does NOT revoke grants: the owner does that through
        the kernel, so money operations stay in one place (ADR-0009 C2)."""
        pid = _uuid(principal_id, "principal")
        with P(request).connection() as c:
            row = c.execute("SELECT disabled_at FROM principals WHERE id = %s FOR UPDATE", (pid,)).fetchone()
            if row is None:
                raise kernel.NotFound("principal not found", code="PRINCIPAL_NOT_FOUND")
            already = row["disabled_at"] is not None
            if not already:
                c.execute("UPDATE principals SET disabled_at = clock_timestamp() WHERE id = %s", (pid,))
                write_audit(c, None, "PRINCIPAL_DISABLED", None, pid)
        return {"principal_id": str(pid), "disabled": True, "already": already}

    @app.post("/me/rotate-key")
    def rotate_key(request: Request, me: Principal = Caller):
        """Issue a new key. The hash is replaced by ONE UPDATE, so the old key stops working at once. The raw key is
        returned once; the audit row carries no key material."""
        raw = new_key()
        with P(request).connection() as c:
            row = c.execute("UPDATE principals SET api_key_hash = %s, key_rotated_at = clock_timestamp()"
                            " WHERE id = %s RETURNING key_expires_at", (hash_key(raw), me.id)).fetchone()
            write_audit(c, None, "KEY_ROTATED", me.id, me.id)
        return _jsonable({"api_key": raw, "key_expires_at": row["key_expires_at"]})

    @app.get("/health")
    def health(request: Request):
        with P(request).connection() as c:
            c.execute("SELECT 1")
        return {"ok": True}

    # ------------------------------------------------------------- kernel operations

    @app.post("/mandates", status_code=201)
    def create_mandate(body: schemas.CreateMandate, request: Request, me: Principal = Caller):
        out = kernel.create_mandate(P(request), owner_principal_id=me.id, currency=body.currency, total=body.total,
                                    protected_reserve=body.protected_reserve, expires_at=body.expires_at,
                                    scope=body.scope.model_dump(exclude_none=True))
        return _jsonable(out)

    @app.post("/mandates/{mandate_id}/settlers", status_code=201)
    def bind_settler(mandate_id: str, body: schemas.BindSettler, request: Request, me: Principal = Caller):
        return _jsonable(kernel.bind_settler(P(request), mandate_id=_uuid(mandate_id, "mandate"), actor=me.id,
                                             principal_id=_uuid(body.principal_id, "principal")))

    @app.post("/grants", status_code=201)
    def delegate(body: schemas.Delegate, request: Request, me: Principal = Caller):
        out = kernel.delegate(P(request), parent_grant_id=_uuid(body.parent_grant_id, "grant"), actor=me.id,
                              holder_principal_id=_uuid(body.holder_principal_id, "principal"), amount=body.amount,
                              expires_at=body.expires_at, scope=body.scope.model_dump(exclude_none=True),
                              idempotency_key=body.idempotency_key)
        return _jsonable(out)

    @app.post("/transactions/authorize")
    def authorize(body: schemas.Authorize, request: Request, me: Principal = Caller):
        out = kernel.authorize(P(request), grant_id=_uuid(body.grant_id, "grant"), actor=me.id, amount=body.amount,
                               currency=body.currency, recipient=body.recipient, category=body.category,
                               idempotency_key=body.idempotency_key, needs_review=body.needs_review)
        return _jsonable(out)

    @app.post("/transactions/{tx_id}/release")
    def release(tx_id: str, request: Request, me: Principal = Caller):
        return _jsonable(kernel.release(P(request), transaction_id=_uuid(tx_id, "transaction"), actor=me.id))

    @app.post("/transactions/{tx_id}/settle")
    def settle(tx_id: str, request: Request, me: Principal = Caller):
        """Simulated: submit + confirm. Testnet mode (BK_SETTLEMENT_MODE=testnet): the adapter signs, broadcasts and
        confirms on proof; calling again advances the same transfer. Permission is enforced by the kernel either way."""
        tid = _uuid(tx_id, "transaction")
        st = request.app.state.settlement
        if st is None:
            kernel.settle_start(P(request), transaction_id=tid, actor=me.id)
            return _jsonable(kernel.settle_confirm(P(request), transaction_id=tid, actor=me.id))
        from budget_kernel.settlement.adapter import SettlementRefused, settle as chain_settle
        if me.kind != "service":                     # a real transfer must be run by a bound settler, never the owner
            raise kernel.Forbidden("testnet settlement requires a service principal", code="NOT_SETTLER")
        chain, signer, cfg = st
        try:
            return _jsonable(chain_settle(P(request), transaction_id=tid, actor=me.id, chain=chain, signer=signer, cfg=cfg))
        except SettlementRefused as e:
            raise HTTPException(409, {"code": "SETTLEMENT_REFUSED", "message": str(e)}) from None

    @app.post("/settlement/reconcile", dependencies=[Depends(require_admin)])
    def settlement_reconcile(request: Request, me: Principal = Caller):
        """Advance every unfinished transfer (re-broadcasts the stored bytes; never re-signs)."""
        st = request.app.state.settlement
        if st is None:
            raise HTTPException(409, {"code": "NOT_TESTNET_MODE", "message": "BK_SETTLEMENT_MODE is not testnet"})
        from budget_kernel.settlement.adapter import reconcile
        return _jsonable({"results": reconcile(P(request), actor=me.id, chain=st[0], cfg=st[2])})

    @app.post("/transactions/{tx_id}/settle-fail")
    def settle_fail(tx_id: str, body: schemas.SettleFail, request: Request, me: Principal = Caller):
        return _jsonable(kernel.settle_fail(P(request), transaction_id=_uuid(tx_id, "transaction"), actor=me.id,
                                            proof=body.proof))

    @app.post("/transactions/{tx_id}/review")
    def review(tx_id: str, body: schemas.Review, request: Request, me: Principal = Caller):
        """Mandate owner approves or denies a 'proposed' (needs-review) transaction."""
        return _jsonable(kernel.review(P(request), transaction_id=_uuid(tx_id, "transaction"), actor=me.id,
                                       approve=body.approve))

    @app.post("/grants/{grant_id}/suspend")
    def suspend_grant(grant_id: str, request: Request, me: Principal = Caller):
        return _jsonable(kernel.suspend(P(request), grant_id=_uuid(grant_id, "grant"), actor=me.id))

    @app.post("/grants/{grant_id}/reinstate")
    def reinstate_grant(grant_id: str, request: Request, me: Principal = Caller):
        return _jsonable(kernel.reinstate(P(request), grant_id=_uuid(grant_id, "grant"), actor=me.id))

    @app.post("/grants/{grant_id}/revoke")
    def revoke(grant_id: str, request: Request, me: Principal = Caller):
        return _jsonable(kernel.revoke(P(request), grant_id=_uuid(grant_id, "grant"), actor=me.id))

    # ------------------------------------------------------------- language interface (never authorizes by itself)

    def _grant_context(request: Request, grant_id: uuid.UUID, me: Principal) -> dict:
        with P(request).connection() as c:
            g = c.execute("SELECT g.holder_principal_id, g.scope, m.owner_principal_id, m.currency,"
                          " EXISTS (SELECT 1 FROM grants a WHERE a.id = ANY(g.path) AND a.status = 'suspended') AS suspended"
                          " FROM grants g JOIN mandates m ON m.id = g.mandate_id WHERE g.id = %s", (grant_id,)).fetchone()
        if g is None:
            raise kernel.NotFound("grant not found", code="GRANT_NOT_FOUND")
        if me.id not in (g["holder_principal_id"], g["owner_principal_id"]):
            raise kernel.Forbidden("not the holder or owner of this grant", code="NOT_PERMITTED")
        if g["suspended"]:      # circuit breaker (ADR-0009): a suspended grant costs no inference either
            raise kernel.Conflict("this grant is suspended", code="GRANT_SUSPENDED")
        return g

    def _interpret(request: Request, g: dict, text: str) -> dict:
        return run_interpret(P(request), request.app.state.card, text, recipients=g["scope"]["recipients"],
                             categories=g["scope"]["categories"], currency=g["currency"].strip(),
                             transport=request.app.state.llm_transport)

    @app.post("/interpret")
    def interpret_only(body: schemas.Interpret, request: Request, me: Principal = Caller):
        """Natural language -> UNTRUSTED typed proposal. This endpoint never reserves or authorizes."""
        g = _grant_context(request, _uuid(body.grant_id, "grant"), me)
        return _jsonable(_interpret(request, g, body.text))

    @app.post("/agent/request")
    def agent_request(body: schemas.AgentRequest, request: Request, me: Principal = Caller):
        """End to end: interpret the request, then let the deterministic kernel decide.

        The kernel receives plain values only (amount, currency, recipient, category), never the model's
        proposal object as authority. Anything not cleanly resolved is held for human review (no funds
        reserved); unresolved interpretation never reaches the kernel at all."""
        gid = _uuid(body.grant_id, "grant")
        g = _grant_context(request, gid, me)
        if me.id != g["holder_principal_id"]:        # before any lookup or model call: a non-holder learns nothing
            raise kernel.Forbidden("only the grant holder may authorize spends", code="NOT_GRANT_HOLDER")
        replay = stored_replay(P(request), grant_id=gid, idempotency_key=body.idempotency_key, text=body.text)
        if replay is not None:                       # BK-305: a retry returns the stored decision, zero model calls
            return _jsonable(replay)
        if injection_suspected(body.text) and me.id == g["holder_principal_id"]:
            kernel.record_signal(P(request), grant_id=gid, actor=me.id, kind="INJECTION", reason="INJECTION_SUSPECTED")
        return _jsonable(interpret_then_decide(
            P(request), request.app.state.card, grant_id=gid, actor=me.id, text=body.text,
            idempotency_key=body.idempotency_key, recipients=g["scope"]["recipients"],
            categories=g["scope"]["categories"], currency=g["currency"].strip(),
            transport=request.app.state.llm_transport))

    # ------------------------------------------------------------- attack demo (baseline vs kernel)

    @app.get("/simulation/scenarios")
    def simulation_list(me: Principal = Caller):
        return {"scenarios": sorted(simulation.SCENARIOS)}

    @app.post("/simulation/run")
    def simulation_run(body: schemas.SimulationRun, request: Request, me: Principal = Caller):
        """Run a named attack against the unsafe baseline AND the real kernel; returns measured outcomes.
        Uses its own fresh mandate and keyless simulation identities; human principals only."""
        if me.kind != "human":
            raise kernel.Forbidden("only human principals may run simulations", code="HUMAN_ONLY")
        if body.scenario not in simulation.SCENARIOS:
            raise kernel.NotFound("unknown scenario", code="UNKNOWN_SCENARIO")
        return _jsonable(simulation.run(P(request), body.scenario))

    @app.get("/budget")
    def budget(request: Request, me: Principal = Caller):
        """Inference budget meter (micro-USD per bucket)."""
        return _jsonable(cost_ledger.snapshot(P(request)))

    # ------------------------------------------------------------- read models

    def _require_viewer(c, mandate_id: uuid.UUID, me: Principal) -> dict:
        m = c.execute("SELECT * FROM mandates WHERE id = %s", (mandate_id,)).fetchone()
        if m is None:
            raise kernel.NotFound("mandate not found", code="MANDATE_NOT_FOUND")
        if m["owner_principal_id"] != me.id and me.kind != "service":
            holds = c.execute("SELECT 1 FROM grants WHERE mandate_id = %s AND holder_principal_id = %s LIMIT 1",
                              (mandate_id, me.id)).fetchone()
            if holds is None:
                raise kernel.Forbidden("not a participant in this mandate", code="NOT_PERMITTED")
        return m

    @app.get("/me")
    def whoami(me: Principal = Caller):
        """Who the API key belongs to (lets a client sign in with a key alone)."""
        return {"principal_id": str(me.id), "name": me.name, "kind": me.kind}

    @app.get("/mandates")
    def my_mandates(request: Request, me: Principal = Caller):
        """Mandates the caller may view: owned, or holding a grant in (service principals see all, as in /state)."""
        with P(request).connection() as c:
            rows = c.execute(
                "SELECT m.id, m.currency, m.total, m.status, m.expires_at, m.created_at,"
                " (m.owner_principal_id = %(me)s) AS is_owner FROM mandates m"
                " WHERE m.owner_principal_id = %(me)s OR %(svc)s"
                " OR EXISTS (SELECT 1 FROM grants g WHERE g.mandate_id = m.id AND g.holder_principal_id = %(me)s)"
                " ORDER BY m.created_at DESC LIMIT 50", {"me": me.id, "svc": me.kind == "service"}).fetchall()
        return _jsonable({"mandates": [{**r, "role": "owner" if r["is_owner"] else "holder"} for r in rows]})

    @app.get("/mandates/{mandate_id}/state")
    def state(mandate_id: str, request: Request, me: Principal = Caller):
        mid = _uuid(mandate_id, "mandate")
        with P(request).connection() as c:
            m = _require_viewer(c, mid, me)
            grants = c.execute("SELECT id, parent_id, depth, holder_principal_id, available, reserved, settled, status,"
                               " expires_at, scope, suspended_at, suspend_reason FROM grants WHERE mandate_id = %s"
                               " ORDER BY depth, created_at", (mid,)).fetchall()
            strikes = {r["grant_id"]: r["n"] for r in c.execute(      # ADR-0009 B4: the count the breaker would use
                "SELECT s.grant_id, sum(s.weight)::int AS n FROM grant_strikes s JOIN grants g ON g.id = s.grant_id"
                " WHERE s.mandate_id = %s AND s.created_at > clock_timestamp() - make_interval(secs => %s)"
                " AND (g.reinstated_at IS NULL OR s.created_at > g.reinstated_at) GROUP BY s.grant_id",
                (mid, breaker.STRIKE_WINDOW_SECONDS))}
            for g in grants:
                g["strikes_in_window"] = strikes.get(g["id"], 0)
            txs = c.execute("SELECT t.id, t.grant_id, t.amount, t.currency, t.recipient, t.category, t.state,"
                            " t.reject_reason, t.review_reason, t.proposal, t.reserve_expires_at, t.created_at, s.tx_hash,"
                            " s.status AS chain_status, s.block_number FROM transactions t"
                            " LEFT JOIN chain_settlements s ON s.transaction_id = t.id WHERE t.mandate_id = %s"
                            " ORDER BY t.created_at DESC LIMIT 200", (mid,)).fetchall()
            for t in txs:                              # BK-315: explorer link for the dashboard (derived, never stored)
                t["explorer_url"] = EXPLORER + t["tx_hash"] if t["tx_hash"] else None
            # window_used is computed here, never in the browser (ADR-0008 section 6): the same subtree sum the
            # kernel uses, measured now. Read-only; the kernel re-checks under the lock when it decides.
            for g in grants:
                sc = g["scope"]
                if "window_limit" in sc:
                    g["window_used"] = c.execute(
                        "SELECT coalesce(sum(t.amount), 0)::bigint AS s FROM transactions t"
                        " JOIN grants x ON x.id = t.grant_id WHERE t.mandate_id = %s AND x.path @> ARRAY[%s]::uuid[]"
                        " AND t.state IN ('reserved','submitted','settled')"
                        " AND t.reserved_at > clock_timestamp() - make_interval(secs => %s)",
                        (mid, g["id"], sc["window_seconds"])).fetchone()["s"]
        violations = kernel.check_invariants(P(request), mid)
        return _jsonable({"mandate": m, "grants": grants, "transactions": txs,
                          "invariants": {"ok": not violations, "violations": violations}})

    @app.get("/mandates/{mandate_id}/integrity")
    def integrity_check(mandate_id: str, request: Request, authorization: str = Header(default=""),
                        x_admin_token: str = Header(default="")):
        """Recompute the mandate's hash chain (ADR-0009 A4). Mandate owner or admin token only."""
        mid = _uuid(mandate_id, "mandate")
        expected = os.environ.get("BK_ADMIN_TOKEN", "")
        if not (expected and hmac.compare_digest(x_admin_token, expected)):
            me = current_principal(request, authorization)
            with P(request).connection() as c:
                m = c.execute("SELECT owner_principal_id FROM mandates WHERE id = %s", (mid,)).fetchone()
            if m is None:
                raise kernel.NotFound("mandate not found", code="MANDATE_NOT_FOUND")
            if m["owner_principal_id"] != me.id:
                raise kernel.Forbidden("only the mandate owner may verify its history", code="NOT_OWNER")
        out = integrity.verify(P(request), mid)
        if out["last_anchor"] and out["last_anchor"]["tx_hash"]:
            out["last_anchor"]["explorer_url"] = EXPLORER + out["last_anchor"]["tx_hash"]
        return _jsonable(out)

    @app.get("/mandates/{mandate_id}/audit")
    def audit(mandate_id: str, request: Request, me: Principal = Caller, after_id: int = 0, limit: int = 200):
        mid = _uuid(mandate_id, "mandate")
        with P(request).connection() as c:
            _require_viewer(c, mid, me)
            rows = c.execute("SELECT id, kind, actor_principal_id, subject_id, detail, created_at FROM audit_events"
                             " WHERE mandate_id = %s AND id > %s ORDER BY id LIMIT %s",
                             (mid, after_id, max(1, min(limit, 500)))).fetchall()
        return _jsonable({"events": rows})

    return app


app = create_app()
