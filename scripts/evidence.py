"""Execution evidence pack (deliverable 6): export every real testnet settlement to evidence/ as JSON + Markdown.

    uv run --project backend python scripts/evidence.py [--schema bk]

Reads the DB directly (read-only). Only confirmed on-chain transfers are listed; nothing is invented.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool

OUT = Path(__file__).resolve().parents[1] / "evidence"
EXPLORER = "https://sepolia-explorer.base.org/tx/"


def collect(pool) -> list[dict]:
    with pool.connection() as c:
        rows = c.execute(
            "SELECT t.id, t.mandate_id, t.grant_id, t.amount, t.currency, t.recipient, t.category, t.state,"
            " s.chain_id, s.from_address, s.to_address, s.token_address, s.token_amount, s.tx_hash, s.nonce,"
            " s.block_number, s.confirmed_at FROM chain_settlements s JOIN transactions t ON t.id = s.transaction_id"
            " WHERE s.status = 'confirmed' ORDER BY s.confirmed_at").fetchall()
        for r in rows:
            r["explorer_url"] = EXPLORER + r["tx_hash"]
            r["audit"] = c.execute(
                "SELECT id, kind, created_at, detail FROM audit_events WHERE mandate_id = %s AND (subject_id = %s OR subject_id = %s)"
                " ORDER BY id", (r["mandate_id"], str(r["id"]), r["id"])).fetchall()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=None)
    a = ap.parse_args()
    st = Settings.load()
    rows = collect(make_pool(st, a.schema or st.schema))
    OUT.mkdir(exist_ok=True)
    (OUT / "settlements.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    md = [f"# Execution evidence: Base Sepolia settlements\n",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. {len(rows)} confirmed transfer(s). Testnet only.\n"]
    for r in rows:
        md += [f"## Kernel transaction `{r['id']}`", f"- Amount: {r['amount']} {r['currency'].strip()} minor units "
               f"({int(r['token_amount']) / 1e6} test USDC) to `{r['recipient']}` (`{r['to_address']}`)",
               f"- From: `{r['from_address']}`  chain {r['chain_id']}  nonce {r['nonce']}",
               f"- Tx hash: `{r['tx_hash']}`", f"- Explorer: {r['explorer_url']}",
               f"- Block {r['block_number']}, confirmed {r['confirmed_at']}", "- Audit trail: " +
               ", ".join(f"{e['kind']}#{e['id']}" for e in r["audit"]), ""]
    (OUT / "SETTLEMENTS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {len(rows)} settlement(s) to {OUT}")


if __name__ == "__main__":
    main()
