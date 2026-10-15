"use client";
import { useEffect, useState } from "react";
import { ApiError, getState, money, type Grant, type MandateState } from "@/lib/api";
import { useSession } from "@/lib/session";

function childrenOf(grants: Grant[], parent: string | null) {
  return grants.filter((g) => g.parent_id === parent);
}

function GrantNode({ g, all, cur }: { g: Grant; all: Grant[]; cur: string }) {
  const kids = childrenOf(all, g.id);
  const tone = g.status === "active" ? "text-ok" : "text-bad";
  return (
    <li>
      <div className="rounded-lg border border-line bg-card p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs text-muted">{g.id.slice(0, 8)}</span>
          <span className={`text-xs font-medium uppercase ${tone}`}>{g.status}</span>
        </div>
        <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
          <div><dt className="text-xs text-muted">Available</dt><dd>{money(g.available, cur)}</dd></div>
          <div><dt className="text-xs text-muted">Reserved</dt><dd>{money(g.reserved, cur)}</dd></div>
          <div><dt className="text-xs text-muted">Settled</dt><dd>{money(g.settled, cur)}</dd></div>
        </dl>
        <p className="mt-2 text-xs text-muted">
          Expires {new Date(g.expires_at).toLocaleString()} · per-tx limit {money(g.scope.per_tx_limit, cur)}
        </p>
      </div>
      {kids.length > 0 && (
        <ul className="ml-3 mt-2 flex flex-col gap-2 border-l border-line pl-3">
          {kids.map((k) => <GrantNode key={k.id} g={k} all={all} cur={cur} />)}
        </ul>
      )}
    </li>
  );
}

export default function MandateView() {
  const { session } = useSession();
  const [state, setState] = useState<MandateState | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!session) return;
    let live = true;
    getState(session.key, session.mandateId)
      .then((st) => { if (live) { setState(st); setErr(null); } })
      .catch((e) => { if (live) setErr(e instanceof ApiError ? `${e.code}: ${e.message}` : "Could not load the mandate"); });
    return () => { live = false; };
  }, [session, tick]);

  if (!state) return <p className="p-4 text-sm text-muted">{err ?? "Loading…"}</p>;
  const cur = state.mandate.currency;
  const inv = state.invariants;
  const roots = childrenOf(state.grants, null);

  return (
    <section className="flex flex-col gap-4">
      <div
        role="status"
        className={`rounded-lg border px-4 py-3 ${inv.ok ? "border-ok/40 bg-ok/10 text-ok" : "border-bad/40 bg-bad/10 text-bad"}`}
      >
        <p className="text-base font-semibold">
          {inv.ok ? "Ledger invariants hold" : `Invariant VIOLATION (${inv.violations.length})`}
        </p>
        <p className="text-xs opacity-80">Checked by the server on this refresh.</p>
        {!inv.ok && <pre className="mt-2 whitespace-pre-wrap text-xs">{JSON.stringify(inv.violations, null, 2)}</pre>}
      </div>
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs text-muted">Mandate total · protected reserve</p>
          <p className="text-lg font-semibold">
            {money(state.mandate.total, cur)}{" "}
            <span className="text-sm font-normal text-muted">· {money(state.mandate.protected_reserve, cur)}</span>
          </p>
        </div>
        <button onClick={() => setTick((t) => t + 1)} className="btn-ghost">Refresh</button>
      </div>
      {err && <p role="alert" className="text-sm text-bad">{err}</p>}
      <ul className="flex flex-col gap-2">
        {roots.map((g) => <GrantNode key={g.id} g={g} all={state.grants} cur={cur} />)}
      </ul>
    </section>
  );
}
