"""Accounting invariants from ADR-0004. Read-only; call after every operation in tests."""
from __future__ import annotations

_RESERVED_BACKED = "coalesce(sum(t.amount) FILTER (WHERE t.state IN ('reserved','submitted')), 0)::bigint"
_SETTLED_BACKED = "coalesce(sum(t.amount) FILTER (WHERE t.state = 'settled'), 0)::bigint"


def check_invariants(pool, mandate_id) -> list[str]:
    """Return a list of violations (empty list = all hold). Uses one consistent snapshot.

    I1 conservation, I2 reservation backing, I3 settlement backing (ADR-0004) and I5: replaying the
    append-only ledger_movements log reproduces every grant's available/reserved/settled exactly."""
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            m = conn.execute("SELECT total, protected_reserve FROM mandates WHERE id = %s", (mandate_id,)).fetchone()
            if m is None:
                return ["mandate missing"]
            out: list[str] = []
            s = conn.execute(
                "SELECT coalesce(sum(available + reserved + settled), 0)::bigint AS s FROM grants WHERE mandate_id = %s",
                (mandate_id,),
            ).fetchone()["s"]
            if m["total"] != m["protected_reserve"] + s:
                out.append(f"I1 conservation: total={m['total']} != reserve {m['protected_reserve']} + grants {s}")
            for r in conn.execute(
                f"SELECT g.id, g.reserved, {_RESERVED_BACKED} AS backed"
                " FROM grants g LEFT JOIN transactions t ON t.grant_id = g.id WHERE g.mandate_id = %s"
                f" GROUP BY g.id, g.reserved HAVING g.reserved <> {_RESERVED_BACKED}",
                (mandate_id,),
            ):
                out.append(f"I2 reservation backing: grant {r['id']} reserved={r['reserved']} backed={r['backed']}")
            for r in conn.execute(
                f"SELECT g.id, g.settled, {_SETTLED_BACKED} AS backed"
                " FROM grants g LEFT JOIN transactions t ON t.grant_id = g.id WHERE g.mandate_id = %s"
                f" GROUP BY g.id, g.settled HAVING g.settled <> {_SETTLED_BACKED}",
                (mandate_id,),
            ):
                out.append(f"I3 settlement backing: grant {r['id']} settled={r['settled']} backed={r['backed']}")
            flows = {(r["gid"], r["b"]): r["s"] for r in conn.execute(
                "WITH f AS ("
                " SELECT to_grant_id AS gid, to_bucket AS b, amount AS a FROM ledger_movements"
                "  WHERE mandate_id = %s AND to_grant_id IS NOT NULL"
                " UNION ALL"
                " SELECT from_grant_id, from_bucket, -amount FROM ledger_movements"
                "  WHERE mandate_id = %s AND from_grant_id IS NOT NULL)"
                " SELECT gid, b, sum(a)::bigint AS s FROM f GROUP BY gid, b", (mandate_id, mandate_id))}
            for g in conn.execute("SELECT id, available, reserved, settled FROM grants WHERE mandate_id = %s",
                                  (mandate_id,)):
                for b in ("available", "reserved", "settled"):
                    if flows.get((g["id"], b), 0) != g[b]:
                        out.append(f"I5 ledger reconciliation: grant {g['id']} {b}={g[b]} movements={flows.get((g['id'], b), 0)}")
            return out
