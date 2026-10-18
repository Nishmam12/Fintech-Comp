"use client";
import { money, reasonText, reasonTitle, type Grant, type Transaction } from "@/lib/api";
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

function BudgetBar({ grants, total, reserve, cur }: { grants: Grant[]; total: number; reserve: number; cur: string }) {
  const sum = (f: (g: Grant) => number) => grants.reduce((a, g) => a + f(g), 0);
  const parts = [
    { key: "settled", label: "Spent", value: sum((g) => g.settled), color: "bg-ink" },
    { key: "reserved", label: "Reserved for pending payments", value: sum((g) => g.reserved), color: "bg-warn" },
    { key: "available", label: "Free to spend", value: sum((g) => g.available), color: "bg-accent" },
    { key: "reserve", label: "Protected reserve", value: reserve, color: "bg-ok" },
  ];
  const whole = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <div className="panel p-5 lg:p-6">
      <p className="text-sm text-muted">Mandate total</p>
      <p className="fig text-4xl lg:text-5xl">{money(total, cur)}</p>
      <div
        role="img"
        aria-label={parts.map((p) => `${p.label} ${money(p.value, cur)}`).join(", ")}
        className="mt-5 flex h-4 w-full gap-0.5 overflow-hidden rounded-full bg-line"
      >
        {parts.map((p) => p.value > 0 && <span key={p.key} className={p.color} style={{ width: `${(p.value / whole) * 100}%` }} />)}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        {parts.map((p) => (
          <li key={p.key} className="flex items-start gap-2">
            <span className={`mt-1.5 size-2.5 shrink-0 rounded-full ${p.color}`} aria-hidden />
            <span>
              <span className="block text-sm text-muted">{p.label}</span>
              <span className="fig text-lg">{money(p.value, cur)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GrantNode({ g, all, cur, me, owner }: { g: Grant; all: Grant[]; cur: string; me: string; owner: string }) {
  const kids = childrenOf(all, g.id);
  const tone = g.status === "active" ? "bg-ok/12 text-ok" : g.status === "suspended" ? "bg-warn/15 text-warn" : "bg-bad/12 text-bad";
  const frozen = g.status === "active" && frozenByAncestor(g, all);
  return (
    <li>
      <div className="panel p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs text-muted">Grant {g.id.slice(0, 8)}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${tone}`}>{g.status}</span>
        </div>
        <dl className="mt-3 grid grid-cols-3 gap-2">
          <div><dt className="text-sm text-muted">Available</dt><dd className="fig whitespace-nowrap text-base sm:text-lg">{money(g.available, cur)}</dd></div>
          <div><dt className="text-sm text-muted">Reserved</dt><dd className="fig whitespace-nowrap text-base sm:text-lg">{money(g.reserved, cur)}</dd></div>
          <div><dt className="text-sm text-muted">Settled</dt><dd className="fig whitespace-nowrap text-base sm:text-lg">{money(g.settled, cur)}</dd></div>
        </dl>
        <p className="mt-2 text-xs text-muted">
          Expires {new Date(g.expires_at).toLocaleString()} · per-tx limit {money(g.scope.per_tx_limit, cur)}
        </p>
        <Velocity g={g} cur={cur} />
        {g.status === "suspended" && (
          <p role="status" className="mt-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm">
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
        <ul className="ml-4 mt-2 flex flex-col gap-2 border-l-2 border-line pl-4">
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
      <BudgetBar grants={state.grants} total={state.mandate.total} reserve={state.mandate.protected_reserve} cur={cur} />
      {err && <p role="alert" className="text-sm text-bad">{err}</p>}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="fig text-xl">Grants</h2>
            <button onClick={refresh} className="btn-ghost">Refresh</button>
          </div>
          <ul className="flex flex-col gap-2">
            {roots.map((g) => <GrantNode key={g.id} g={g} all={state.grants} cur={cur} me={me} owner={owner} />)}
          </ul>
        </div>
        <div className="flex flex-col gap-4">
          <div
            role="status"
            className={`rounded-lg border px-4 py-3 ${inv.ok ? "border-ok/40 bg-ok/10 text-ok" : "border-bad/40 bg-bad/10 text-bad"}`}
          >
            <p className="text-base font-semibold">
              {inv.ok ? "Ledger invariants hold" : `Invariant VIOLATION (${inv.violations.length})`}
            </p>
            <p className="text-sm opacity-80">Checked by the server on this refresh.</p>
            {!inv.ok && <pre className="mt-2 whitespace-pre-wrap text-xs">{JSON.stringify(inv.violations, null, 2)}</pre>}
          </div>
          <IntegrityBadge />
          <div className="panel p-4">
            <h2 className="fig text-xl">Transactions</h2>
            {state.transactions.length === 0 && <p className="mt-2 text-sm text-muted">No transactions yet. Ask for a payment to see the kernel decide.</p>}
            <ul className="mt-3 flex flex-col divide-y divide-line">
              {state.transactions.slice(0, 30).map((t) => {
                const tt = t.state === "rejected" ? "text-bad" : t.state === "held" ? "text-warn" : "text-ok";
                return (
                  <li key={t.id} className="py-2.5">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="fig text-lg">{money(t.amount, t.currency || cur)}</span>
                      <span className={`text-sm font-semibold capitalize ${tt}`}>{t.state}</span>
                    </div>
                    <p className="wrap-anywhere text-sm text-muted">
                      {t.recipient} · {t.category}
                      {t.reject_reason && <> · <span title={reasonTitle(t.reject_reason)}>{reasonText(t.reject_reason)}</span></>}
                    </p>
                    <TxLink t={t} />
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
