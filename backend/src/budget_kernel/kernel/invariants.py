"""Accounting invariants from ADR-0004. Read-only; call after every operation in tests."""
from __future__ import annotations

_RESERVED_BACKED = "coalesce(sum(t.amount) FILTER (WHERE t.state IN ('reserved','submitted')), 0)::bigint"
_SETTLED_BACKED = "coalesce(sum(t.amount) FILTER (WHERE t.state = 'settled'), 0)::bigint"


def check_invariants(pool, mandate_id) -> list[str]:
    """Return a list of violations (empty list = all hold). Uses one consistent snapshot."""
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
            return out
