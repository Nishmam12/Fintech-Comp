"use client";
// Screen 1 on the revision 3 system: a cheque for the mandate (amount, seal, allocation), then two equal halves,
// "Who may spend" (the grant tree as ledger rows) and "Decisions" (each proposal beside the kernel's verdict).
import { useState } from "react";
import { grantName, money, reasonText, type Grant, type Transaction } from "@/lib/api";
import IntegrityBadge from "@/components/IntegrityBadge";
import RevokeControl from "@/components/RevokeControl";
import SuspendControl from "@/components/SuspendControl";
import Cheque from "@/components/ui/Cheque";
import ProposalVerdict from "@/components/ui/ProposalVerdict";
import Section, { Filler } from "@/components/ui/Section";
import type { Tone } from "@/components/ui/Stamp";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

const COLS = "minmax(0,1fr) 6rem 6rem 6rem 2.5rem";

// money() gives "1,000.00 USD"; the cheque shows the figure large and the currency small.
const figure = (minor: number, cur: string) => money(minor, cur).replace(/\s+\S+$/, "");
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// Grants in tree order (parents before their children) so depth indents read as nesting.
function inTreeOrder(grants: Grant[]): Grant[] {
  const out: Grant[] = [];
  const walk = (parent: string | null) => grants.filter((g) => g.parent_id === parent).forEach((g) => { out.push(g); walk(g.id); });
  walk(null);
  return out;
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

function holderLine(g: Grant, all: Grant[]): string {
  const role = g.parent_id === null ? "Owner's root grant" : g.scope.can_delegate ? "Manager" : "Agent";
  const bits = [role];
  if (g.status === "suspended") bits.push("suspended");
  else if (g.status === "revoked") bits.push("revoked");
  else if (frozenByAncestor(g, all)) bits.push("frozen by a grant above");
  else if (g.strikes_in_window) bits.push(`${g.strikes_in_window} refused recently`);
  return bits.join(", ");
}

function verdictOf(t: Transaction): { stamp: string; tone: Tone; reason: React.ReactNode; title?: string } {
  switch (t.state) {
    case "rejected":
      { const why = t.reject_reason ? reasonText(t.reject_reason) : "The kernel said no"; return { stamp: "Refused", tone: "no", reason: why, title: why }; }
    case "proposed":
    { const why = t.review_reason ? reasonText(t.review_reason) : "Waiting for the owner"; return { stamp: "Held", tone: "wait", reason: why, title: why }; }
    case "settled": {
      const link = t.explorer_url?.startsWith("https://") ? t.explorer_url : null; // only the API's https link
      return { stamp: "Paid", tone: "ok", reason: link ? <>Settled, <a href={link} target="_blank" rel="noopener noreferrer">view on explorer</a></> : "Settled" };
    }
    case "submitted": return { stamp: "Sending", tone: "wait", reason: "Payment sent, waiting to confirm" };
    case "released": return { stamp: "Released", tone: "dim", reason: "The reservation was released" };
    default: return { stamp: "Approved", tone: "ok", reason: "Money reserved for this payment" };
  }
}

function Allocation({ grants, total, reserve, cur }: { grants: Grant[]; total: number; reserve: number; cur: string }) {
  const sum = (f: (g: Grant) => number) => grants.reduce((a, g) => a + f(g), 0);
  const parts = [
    { label: "Spent", value: sum((g) => g.settled), style: { background: "var(--ink)" }, cls: "" },
    { label: "Waiting to settle", value: sum((g) => g.reserved), style: { background: "var(--held)" }, cls: "" },
    { label: "Free to spend", value: sum((g) => g.available), style: {}, cls: "hatch" },
    { label: "Protected", value: reserve, style: { background: "var(--approve)" }, cls: "" },
  ];
  const whole = parts.reduce((a, p) => a + p.value, 0) || total || 1;
  return (
    <>
      <div className="c12 alloc" role="img" aria-label={parts.map((p) => `${p.label} ${money(p.value, cur)}`).join(", ")}>
        {parts.map((p) => p.value > 0 && <i key={p.label} className={p.cls} style={{ ...p.style, width: `${(p.value / whole) * 100}%` }} />)}
      </div>
      <div className="c12 legend">
        {parts.map((p) => (
          <div key={p.label}>
            <span><i className={`sw ${p.cls}`} style={{ ...p.style, border: p.cls ? "1px solid var(--rule)" : undefined }} />{p.label}</span>
            <b className="fig">{figure(p.value, cur)}</b>
          </div>
        ))}
      </div>
    </>
  );
}

function LedgerRow({ g, all, cur, me, owner }: { g: Grant; all: Grant[]; cur: string; me: string; owner: string }) {
  const [open, setOpen] = useState(false);
  const manageable = canManage(g, all, me, owner);
  const dim = g.status !== "active";
  return (
    <>
      <div className={`row d${Math.min(g.depth, 2)}`} style={{ gridTemplateColumns: COLS, opacity: dim ? 0.7 : 1 }}>
        <div className="name"><b>{g.parent_id === null ? (g.holder_name ?? "Owner") : grantName(g)}</b><em>{holderLine(g, all)}</em></div>
        <span className="num fig">{figure(g.available, cur)}</span>
        <span className="num hide-s">{figure(g.reserved, cur)}</span>
        <span className="num hide-s">{figure(g.settled, cur)}</span>
        {g.parent_id !== null
          ? <button className="more" aria-expanded={open} aria-label={`Manage ${grantName(g)}`} onClick={() => setOpen(!open)}>⋯</button>
          : <span />}
      </div>
      {open && (
        <div className="manage">
          <p className="tag" style={{ margin: "0 0 0.5rem" }}>
            Expires {new Date(g.expires_at).toLocaleDateString()}, up to {money(g.scope.per_tx_limit, cur)} a payment
            {g.scope.review_above !== undefined && <>, approval above {money(g.scope.review_above, cur)}</>}
          </p>
          {manageable ? (
            <>
              <SuspendControl g={g} canManage isOwner={me === owner} />
              <RevokeControl g={g} currency={cur} />
            </>
          ) : (
            <SuspendControl g={g} canManage={false} isOwner={me === owner} />
          )}
        </div>
      )}
    </>
  );
}

export default function MandateView() {
  const { state, error: err, refresh, updatedAt } = useMandate();
  const { session } = useSession();

  if (!state) {
    return <Section span={12} title="Mandate"><p className="tag" style={{ padding: "1rem 0" }}>{err ?? "Loading…"}</p></Section>;
  }
  const m = state.mandate;
  const cur = m.currency;
  const me = session?.principalId ?? "";
  const isOwner = m.owner_principal_id === me;
  const tree = inTreeOrder(state.grants);
  const root = state.grants.find((g) => g.parent_id === null);
  const mine = state.grants.find((g) => g.holder_principal_id === me && g.parent_id !== null);
  const sample = mine ?? [...tree].reverse().find((g) => g.parent_id !== null);
  const serial = m.id.replace(/-/g, "").slice(0, 8).toUpperCase();
  const [whole, unit] = money(m.total, cur).split(/\s+(?=\S+$)/);

  return (
    <>
      <Cheque className="c12" inner="">
        <div className="c12 meta-line">
          <span>Spending mandate{root?.holder_name ? ` issued by ${root.holder_name}` : ""}</span>
          <span className="serial">No. {serial.slice(0, 4)} {serial.slice(4)}, valid to {new Date(m.expires_at).toLocaleDateString([], { dateStyle: "medium" })}</span>
        </div>
        <div className={isOwner ? "c8" : "c12"}>
          <div className="amount fig">{whole}<small>{unit}</small></div>
          <p className="note">
            Agents below may spend within their limits. {money(m.protected_reserve, cur)} is held back and can never be spent.
          </p>
        </div>
        <IntegrityBadge ledgerOk={state.invariants.ok} />
        <Allocation grants={state.grants} total={m.total} reserve={m.protected_reserve} cur={cur} />
      </Cheque>

      <Section
        span={6}
        title="Who may spend"
        className="ledger"
        meta={<>{updatedAt ? `Updated ${hhmm(updatedAt.toISOString())}` : ""} <button className="linkbtn" onClick={refresh}>Refresh</button></>}
        head={
          <div className="row head" style={{ gridTemplateColumns: COLS }}>
            <span>Holder</span><span className="num">Free</span><span className="num hide-s">Reserved</span><span className="num hide-s">Spent</span><span />
          </div>
        }
        foot={sample ? (
          <>
            <span>{grantName(sample)}: up to {figure(sample.scope.per_tx_limit, cur)} a payment</span>
            {sample.scope.review_above !== undefined && <span>approval above {figure(sample.scope.review_above, cur)}</span>}
            {sample.scope.window_limit !== undefined && sample.window_used !== undefined && <span>{figure(sample.window_used, cur)} of {figure(sample.scope.window_limit, cur)} this window</span>}
          </>
        ) : undefined}
      >
        {tree.map((g) => <LedgerRow key={g.id} g={g} all={state.grants} cur={cur} me={me} owner={m.owner_principal_id} />)}
        <Filler>Grants you delegate appear here, nested under the grant they come from.</Filler>
      </Section>

      <Section
        span={6}
        title="Decisions"
        meta="Model proposes, kernel decides"
        foot={<span>{state.transactions.length} decision{state.transactions.length === 1 ? "" : "s"}, newest first</span>}
        head={<div className="row head pairrow"><span>Proposed by the model</span><span /><span>Decided by the kernel</span></div>}
      >
        {err && <p role="alert" className="alert">{err}</p>}
        {state.transactions.slice(0, 40).map((t) => {
          const v = verdictOf(t);
          const holder = state.grants.find((g) => g.id === t.grant_id);
          return (
            <ProposalVerdict
              key={t.id}
              who={`${holder ? grantName(holder) : "Unknown holder"}, ${hhmm(t.created_at)}`}
              proposal={`Pay ${figure(t.amount, t.currency || cur)} to ${t.recipient}, ${t.category}`}
              stamp={v.stamp} tone={v.tone} reason={v.reason} title={v.title}
            />
          );
        })}
        <Filler>Every request an agent sends appears here: what the model read, and what the kernel decided.</Filler>
      </Section>
    </>
  );
}
