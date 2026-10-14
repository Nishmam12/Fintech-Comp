"""HTTP API. Thin layer: authenticate, parse strictly, call the kernel, map errors.

The API never decides anything about money; every decision comes from budget_kernel.kernel.
    uv run uvicorn budget_kernel.api.app:app --reload
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from budget_kernel import kernel
from budget_kernel.costledger import ledger as cost_ledger
from budget_kernel.costledger.rate_card import RateCard
from budget_kernel.routing.interpret import interpret as run_interpret
from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool

from . import schemas
from .auth import Caller, Principal, hash_key, new_key, require_admin


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


def create_app(pool=None, schema: str | None = None, card: RateCard | None = None, llm_transport=None) -> FastAPI:
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
        yield
        if owned:
            app.state.pool.close()

    app = FastAPI(title="Budget Kernel", version="0.1.0", lifespan=lifespan)

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
            row = c.execute("INSERT INTO principals(name, kind, api_key_hash) VALUES (%s,%s,%s) RETURNING id",
                            (body.name, body.kind, hash_key(raw))).fetchone()
        return {"principal_id": str(row["id"]), "api_key": raw, "note": "store this key now; it is not shown again"}

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
                                    scope=body.scope.model_dump())
        return _jsonable(out)

    @app.post("/grants", status_code=201)
    def delegate(body: schemas.Delegate, request: Request, me: Principal = Caller):
        out = kernel.delegate(P(request), parent_grant_id=_uuid(body.parent_grant_id, "grant"), actor=me.id,
                              holder_principal_id=_uuid(body.holder_principal_id, "principal"), amount=body.amount,
                              expires_at=body.expires_at, scope=body.scope.model_dump(),
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
    def settle_simulated(tx_id: str, request: Request, me: Principal = Caller):
        """Simulated settlement: submit + confirm. The testnet adapter (ADR-0007) replaces this path.
        Permission (settlement service, or the mandate owner in simulation) is enforced by the kernel."""
        tid = _uuid(tx_id, "transaction")
        kernel.settle_start(P(request), transaction_id=tid, actor=me.id)
        return _jsonable(kernel.settle_confirm(P(request), transaction_id=tid, actor=me.id))

    @app.post("/transactions/{tx_id}/settle-fail")
    def settle_fail(tx_id: str, body: schemas.SettleFail, request: Request, me: Principal = Caller):
        return _jsonable(kernel.settle_fail(P(request), transaction_id=_uuid(tx_id, "transaction"), actor=me.id,
                                            proof=body.proof))

    @app.post("/transactions/{tx_id}/review")
    def review(tx_id: str, body: schemas.Review, request: Request, me: Principal = Caller):
        """Mandate owner approves or denies a 'proposed' (needs-review) transaction."""
        return _jsonable(kernel.review(P(request), transaction_id=_uuid(tx_id, "transaction"), actor=me.id,
                                       approve=body.approve))

    @app.post("/grants/{grant_id}/revoke")
    def revoke(grant_id: str, request: Request, me: Principal = Caller):
        return _jsonable(kernel.revoke(P(request), grant_id=_uuid(grant_id, "grant"), actor=me.id))

    # ------------------------------------------------------------- language interface (never authorizes by itself)

    def _grant_context(request: Request, grant_id: uuid.UUID, me: Principal) -> dict:
        with P(request).connection() as c:
            g = c.execute("SELECT g.holder_principal_id, g.scope, m.owner_principal_id, m.currency FROM grants g"
                          " JOIN mandates m ON m.id = g.mandate_id WHERE g.id = %s", (grant_id,)).fetchone()
        if g is None:
            raise kernel.NotFound("grant not found", code="GRANT_NOT_FOUND")
        if me.id not in (g["holder_principal_id"], g["owner_principal_id"]):
            raise kernel.Forbidden("not the holder or owner of this grant", code="NOT_PERMITTED")
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
        interp = _interpret(request, g, body.text)
        p = interp["proposal"]
        decision = None
        if interp["status"] in ("ok", "needs_review") and p and p["request_type"] == "payment" and None not in (
                p["amount_minor"], p["currency"], p["recipient"], p["category"]) and not p["missing_fields"]:
            decision = kernel.authorize(
                P(request), grant_id=gid, actor=me.id, amount=p["amount_minor"], currency=p["currency"],
                recipient=p["recipient"], category=p["category"], idempotency_key=body.idempotency_key,
                needs_review=interp["status"] == "needs_review", proposal=p)
        return _jsonable({"interpretation": interp, "decision": decision})

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

    @app.get("/mandates/{mandate_id}/state")
    def state(mandate_id: str, request: Request, me: Principal = Caller):
        mid = _uuid(mandate_id, "mandate")
        with P(request).connection() as c:
            m = _require_viewer(c, mid, me)
            grants = c.execute("SELECT id, parent_id, depth, holder_principal_id, available, reserved, settled, status,"
                               " expires_at, scope FROM grants WHERE mandate_id = %s ORDER BY depth, created_at",
                               (mid,)).fetchall()
            txs = c.execute("SELECT id, grant_id, amount, currency, recipient, category, state, reject_reason,"
                            " reserve_expires_at, created_at FROM transactions WHERE mandate_id = %s"
                            " ORDER BY created_at DESC LIMIT 200", (mid,)).fetchall()
        violations = kernel.check_invariants(P(request), mid)
        return _jsonable({"mandate": m, "grants": grants, "transactions": txs,
                          "invariants": {"ok": not violations, "violations": violations}})

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
