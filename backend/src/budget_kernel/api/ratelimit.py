"""In-process token-bucket rate limiting (ADR-0009 C1). Transport policy only: it never touches money or the kernel,
and a refusal here is not a kernel strike.

Per PROCESS: with several replicas the effective limit is multiplied by the replica count.
Key = the principal id when the bearer key is valid, otherwise the client IP. X-Forwarded-For is ignored unless
BK_TRUST_PROXY=1 (a client could otherwise spoof it to dodge the limit)."""
from __future__ import annotations

import math
import os
import threading
import time
from collections import OrderedDict

from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import SESSION_PREFIX, hash_key

DEFAULT_PER_MIN = 120
MODEL_PER_MIN = 30
AUTH_PER_MIN = 10        # login and sign-up attempts per client IP; the account lockout is a separate, per-account control
MODEL_PATHS = {("POST", "/agent/request"), ("POST", "/interpret")}
AUTH_PATHS = {("POST", "/auth/login"), ("POST", "/auth/signup")}
EXEMPT_PATHS = {"/health"}
MAX_BUCKETS = 50_000     # hard cap on table size; the least recently used bucket is dropped beyond it


def _int_env(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return v if v >= 0 else default


class RateLimiter:
    """limit_per_min = 0 disables that bucket. Buckets hold (tokens, last_seen); idle buckets are dropped as soon as
    they would have refilled completely (a full bucket is the same as no bucket), so memory follows active keys."""

    def __init__(self, default_per_min: int | None = None, model_per_min: int | None = None, *,
                 auth_per_min: int | None = None, clock=time.monotonic, trust_proxy: bool | None = None,
                 max_buckets: int = MAX_BUCKETS):
        self.default_per_min = _int_env("BK_RATE_DEFAULT_PER_MIN", DEFAULT_PER_MIN) if default_per_min is None else default_per_min
        self.model_per_min = _int_env("BK_RATE_MODEL_PER_MIN", MODEL_PER_MIN) if model_per_min is None else model_per_min
        self.auth_per_min = _int_env("BK_RATE_AUTH_PER_MIN", AUTH_PER_MIN) if auth_per_min is None else auth_per_min
        self.trust_proxy = os.environ.get("BK_TRUST_PROXY") == "1" if trust_proxy is None else trust_proxy
        self.clock, self.max_buckets = clock, max_buckets
        self._buckets: OrderedDict[tuple[str, str], tuple[float, float]] = OrderedDict()   # (kind, key) -> (tokens, at)
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._buckets)

    def _peek(self, kind: str, key: str, per_min: int, now: float) -> float:
        tokens, at = self._buckets.get((kind, key), (float(per_min), now))
        return min(float(per_min), tokens + (now - at) * per_min / 60.0)

    def _purge(self, now: float) -> None:
        """Oldest first: drop buckets idle long enough to be full again, then enforce the size cap."""
        limits = {"default": self.default_per_min, "model": self.model_per_min, "auth": self.auth_per_min}
        while self._buckets:
            (kind, _), (tokens, at) = next(iter(self._buckets.items()))
            per_min = limits[kind]
            full = per_min <= 0 or tokens + (now - at) * per_min / 60.0 >= per_min
            if not full and len(self._buckets) <= self.max_buckets:
                break
            self._buckets.popitem(last=False)

    def check(self, key: str, *, model: bool = False, auth: bool = False) -> int | None:
        """Charge one request. None = allowed; otherwise whole seconds to wait (>= 1). Nothing is charged on refusal."""
        with self._lock:
            now = self.clock()
            self._purge(now)
            charges = ([("default", self.default_per_min)] + ([("model", self.model_per_min)] if model else [])
                       + ([("auth", self.auth_per_min)] if auth else []))
            charges = [(k, n) for k, n in charges if n > 0]
            wait = 0.0
            for kind, n in charges:
                have = self._peek(kind, key, n, now)
                if have < 1.0:
                    wait = max(wait, (1.0 - have) * 60.0 / n)
            if wait > 0:
                return max(1, math.ceil(wait))
            for kind, n in charges:
                self._buckets[(kind, key)] = (self._peek(kind, key, n, now) - 1.0, now)
                self._buckets.move_to_end((kind, key))
            return None

    def client_ip(self, request: Request) -> str:
        if self.trust_proxy:
            hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
            if hops:
                return hops[-1]      # the entry our own proxy appended; earlier entries are client-controlled
        return request.client.host if request.client else "unknown"

    def key_for(self, request: Request) -> str:
        scheme, _, raw = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() == "bearer" and raw:
            try:
                with request.app.state.pool.connection() as c:
                    row = c.execute("SELECT id FROM principals WHERE api_key_hash = %s", (hash_key(raw),)).fetchone()
                    if row is None and raw.startswith(SESSION_PREFIX):          # a login session counts against its person
                        row = c.execute("SELECT principal_id AS id FROM sessions WHERE token_hash = %s", (hash_key(raw),)).fetchone()
                if row is not None:
                    return f"p:{row['id']}"
            except Exception:       # a lookup failure must not break requests; fall back to the IP bucket
                pass
        return f"ip:{self.client_ip(request)}"

    async def middleware(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in EXEMPT_PATHS:
            return await call_next(request)
        key = await _in_thread(self.key_for, request)
        wait = self.check(key, model=(request.method, path) in MODEL_PATHS, auth=(request.method, path) in AUTH_PATHS)
        if wait is None:
            return await call_next(request)
        return JSONResponse(status_code=429, headers={"Retry-After": str(wait)}, content={"detail": {
            "code": "RATE_LIMITED", "message": f"too many requests; retry in {wait} s"}})


async def _in_thread(fn, *args):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(fn, *args)
