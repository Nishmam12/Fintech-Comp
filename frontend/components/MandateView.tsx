"use client";
import { money, reasonText, type Grant, type Transaction } from "@/lib/api";
import IntegrityBadge from "@/components/IntegrityBadge";
import RevokeControl from "@/components/RevokeControl";
import SuspendControl from "@/components/SuspendControl";
import { useSession } from "@/lib/session";
import { useMandate } from "@/lib/mandate";

function childrenOf(grants: Grant[], parent: string | null) {
  return grants.filter((g) => g.parent_id === parent);
}

// Velocity meter (BK-324). window_used, window_limit and review_above are shown exactly as the server returned them.
function Velocity({ g, cur }: { g: Grant; cur: string }) {
  const { window_limit: limit, window_seconds: secs, review_above: above } = g.scope;
  if (limit === undefined && above === undefined) return null;
  return (
    <div className="mt-2 text-xs text-muted">
      {limit !== undefined && g.window_used !== undefined && (
        <>
          <div className="flex justify-between">
            <span>Velocity{secs !== undefined ? ` · per ${secs >= 3600 && secs % 3600 === 0 ? `${secs / 3600} h` : `${secs} s`}` : ""}</span>
            <span>{money(g.window_used, cur)} of {money(limit, cur)}</span>
          </div>
          <progress
            className="mt-1 h-2 w-full overflow-hidden rounded [&::-webkit-progress-bar]:bg-line [&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent"
            max={limit}
            value={g.window_used}
            aria-label="Spend in the current window"
          />
        </>
      )}
      {above !== undefined && <p className="mt-1">Needs your approval above {money(above, cur)}</p>}
    </div>
  );
}

function TxLink({ t }: { t: Transaction }) {
  // Only the API-provided link, and only https: model/user text must never become a clickable script URL.
  if (!t.explorer_url || !t.explorer_url.startsWith("https://")) return null;
  return (
    <a href={t.explorer_url} target="_blank" rel="noopener noreferrer" className="text-accent underline">
      View on explorer
    </a>
  );
}

// Owner, or the holder of a grant above this one (the server applies the same rule).
function canManage(g: Grant, all: Grant[], me: string, owner: string): boolean {
  if (me === owner) return true;
  const byId = new Map(all.map((x) => [x.id, x]));
  for (let p = g.parent_id ? byId.get(g.parent_id) : undefined; p; p = p.parent_id ? byId.get(p.parent_id) : undefined) {
    if (p.holder_principal_id === me) return true;
  }
  return false;
}

function frozenByAncestor(g: Grant, all: Grant[]): boolean {
  const byId = new Map(all.map((x) => [x.id, x]));
  for (let p = g.parent_id ? byId.get(g.parent_id) : undefined; p; p = p.parent_id ? byId.get(p.parent_id) : undefined) {
    if (p.status === "suspended") return true;
  }
  return false;
}

function GrantNode({ g, all, cur, me, owner }: { g: Grant; all: Grant[]; cur: string; me: string; owner: string }) {
  const kids = childrenOf(all, g.id);
  const tone = g.status === "active" ? "text-ok" : g.status === "suspended" ? "text-accent" : "text-bad";
  const frozen = g.status === "active" && frozenByAncestor(g, all);
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
        <Velocity g={g} cur={cur} />
        {g.status === "suspended" && (
          <p role="status" className="mt-2 rounded-md border border-accent/40 bg-accent/10 px-3 py-2 text-sm">
            Suspended{g.suspend_reason === "STRIKES" ? " by the circuit breaker (too many refused requests)" : g.suspend_reason === "MANUAL" ? " by hand" : ""}
            {g.suspended_at ? ` · ${new Date(g.suspended_at).toLocaleString()}` : ""}. It cannot spend until reinstated.
          </p>
        )}
        {frozen && (
          <p role="status" className="mt-2 rounded-md border border-line bg-background px-3 py-2 text-sm text-muted">
            Frozen: a grant above this one is suspended.
          </p>
        )}
        {g.status === "active" && !!g.strikes_in_window && (
          <p className="mt-2 text-xs text-muted">Strikes in the current window: {g.strikes_in_window}</p>
        )}
        {g.parent_id !== null && <SuspendControl g={g} canManage={canManage(g, all, me, owner)} isOwner={me === owner} />}
        {g.parent_id !== null && canManage(g, all, me, owner) && <RevokeControl g={g} currency={cur} />}
      </div>
      {kids.length > 0 && (
        <ul className="ml-3 mt-2 flex flex-col gap-2 border-l border-line pl-3">
          {kids.map((k) => <GrantNode key={k.id} g={k} all={all} cur={cur} me={me} owner={owner} />)}
        </ul>
      )}
    </li>
  );
}

export default function MandateView() {
  const { state, error: err, refresh } = useMandate();
  const { session } = useSession();

  if (!state) return <p className="p-4 text-sm text-muted">{err ?? "Loading…"}</p>;
  const cur = state.mandate.currency;
  const inv = state.invariants;
  const roots = childrenOf(state.grants, null);
  const me = session?.principalId ?? "";
  const owner = state.mandate.owner_principal_id;

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
      <IntegrityBadge />
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs text-muted">Mandate total · protected reserve</p>
          <p className="text-lg font-semibold">
            {money(state.mandate.total, cur)}{" "}
            <span className="text-sm font-normal text-muted">· {money(state.mandate.protected_reserve, cur)}</span>
          </p>
        </div>
        <button onClick={refresh} className="btn-ghost">Refresh</button>
      </div>
      {err && <p role="alert" className="text-sm text-bad">{err}</p>}
      <ul className="flex flex-col gap-2">
        {roots.map((g) => <GrantNode key={g.id} g={g} all={state.grants} cur={cur} me={me} owner={owner} />)}
      </ul>
      <div className="rounded-lg border border-line bg-card p-3">
        <h3 className="text-sm font-semibold">Transactions</h3>
        {state.transactions.length === 0 && <p className="mt-2 text-sm text-muted">No transactions yet.</p>}
        <ul className="mt-2 flex flex-col gap-2">
          {state.transactions.slice(0, 30).map((t) => (
            <li key={t.id} className="rounded border border-line px-2 py-1.5 text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{money(t.amount, t.currency || cur)}</span>
                <span className="text-xs uppercase text-muted">{t.state}</span>
              </div>
              <p className="wrap-anywhere text-xs text-muted">
                {t.recipient} · {t.category}
                {t.reject_reason ? ` · ${reasonText(t.reject_reason)}` : ""}
              </p>
              <TxLink t={t} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
