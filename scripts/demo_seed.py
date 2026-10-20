"""Seed a named demo mandate and write one-click sign-in keys for the dashboard (BK-502).

    uv run --project backend python scripts/demo_seed.py [--base-url http://localhost:8000]

Creates, through the API only (reusing the helpers of scripts/demo.py), a fresh mandate every run:
Nabil (owner) 1000.00 USD with 100.00 protected -> Ops bot (manager) 500.00, may delegate -> Research bot (agent) 300.00.
Writes NEXT_PUBLIC_DEMO_KEYS to frontend/.env.local (gitignored; other lines are kept). Prints labels and the
mandate id only, never a key. With BK_SETTLEMENT_MODE=testnet it also binds BK_WORKER_PRINCIPAL as the settler.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo import ROOT, Demo  # noqa: E402

ENV_LOCAL = ROOT / "frontend" / ".env.local"
VAR = "NEXT_PUBLIC_DEMO_KEYS"
# The demo owner is a real password account (username and password, signed in with a login session), so the video and the
# demo show the real sign-in. These are demo credentials on a testnet prototype, not secrets; change them with BK_DEMO_PASSWORD.
DEMO_USER = "nabil"
DEMO_PASSWORD = os.environ.get("BK_DEMO_PASSWORD", "kernel-demo-2026")


def _env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return ""


def write_keys(keys: dict[str, str], path: Path = ENV_LOCAL) -> None:
    """Replace the VAR line, keep every other line."""
    kept = [ln for ln in (path.read_text(encoding="utf-8").splitlines() if path.exists() else [])
            if not ln.startswith(VAR + "=")]
    path.write_text("\n".join(kept + [f"{VAR}={json.dumps(keys, separators=(',', ':'))}"]) + "\n", encoding="utf-8")
    path.chmod(0o600)


def owner_session(d: Demo) -> dict:
    """Create the demo owner as a password account (kept if it already exists) and sign in; the session token is the bearer."""
    r = d.http.post("/admin/accounts", json={"name": "Nabil", "username": DEMO_USER, "password": DEMO_PASSWORD}, headers=d.admin)
    if r.status_code not in (201, 409):
        r.raise_for_status()
    r = d.http.post("/auth/login", json={"username": DEMO_USER, "password": DEMO_PASSWORD})
    if r.status_code != 200:
        sys.exit(f"cannot sign in as {DEMO_USER}: {r.json().get('detail', {}).get('code', r.status_code)} "
                 "(the account exists with another password; set BK_DEMO_PASSWORD to it)")
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def seed(base: str) -> tuple[str, dict[str, str]]:
    d = Demo(base)
    tag = uuid.uuid4().hex[:6]
    nabil = owner_session(d)
    ops_id, ops = d.principal("Ops bot", "agent")
    res_id, res = d.principal("Research bot", "agent")
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0).isoformat()
    base_scope = {"categories": ["cloud", "software"], "recipients": ["aws", "github", "openai"],
                  "per_tx_limit": 20_000, "can_delegate": True}

    def ok(r):
        r.raise_for_status()
        return r.json()

    m = ok(d.post("/mandates", nabil, {"currency": "USD", "total": 100_000, "protected_reserve": 10_000,
                                       "expires_at": expires, "scope": base_scope}))
    ops_grant = ok(d.post("/grants", nabil, {"parent_grant_id": m["root_grant_id"], "holder_principal_id": ops_id,
                                             "amount": 50_000, "expires_at": expires, "scope": base_scope,
                                             "idempotency_key": f"seed-ops-{tag}"}))["grant_id"]
    ok(d.post("/grants", ops, {"parent_grant_id": ops_grant, "holder_principal_id": res_id, "amount": 30_000,
                               "expires_at": expires, "idempotency_key": f"seed-res-{tag}",
                               "scope": {"categories": ["cloud"], "recipients": ["aws", "github", "openai"],
                                         "per_tx_limit": 10_000, "can_delegate": False,
                                         "window_limit": 25_000, "window_seconds": 3600, "review_above": 6_000}}))
    if os.environ.get("BK_SETTLEMENT_MODE") == "testnet" or _env("BK_SETTLEMENT_MODE") == "testnet":
        worker = _env("BK_WORKER_PRINCIPAL")
        if worker:
            ok(d.post(f"/mandates/{m['mandate_id']}/settlers", nabil, {"principal_id": worker}))
        else:
            print("testnet mode but BK_WORKER_PRINCIPAL is unset: no settler bound", file=sys.stderr)
    keys = {"Nabil (owner)": nabil["Authorization"][7:], "Ops bot (manager)": ops["Authorization"][7:],
            "Research bot (agent)": res["Authorization"][7:]}
    return m["mandate_id"], keys


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BK_API_URL", "http://localhost:8000"))
    a = ap.parse_args()
    mandate, keys = seed(a.base_url)
    write_keys(keys)
    print(f"Seeded mandate {mandate}\nSign-in buttons: {', '.join(keys)}\nOwner password sign-in: username {DEMO_USER}, password {DEMO_PASSWORD}\nWrote {ENV_LOCAL.relative_to(ROOT)} (keys not shown)")
