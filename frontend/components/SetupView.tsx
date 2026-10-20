"use client";
// First-run setup for a person who has signed in and has no mandate yet (docs/plans/LOGIN_PLAN.md):
// 1. fund a mandate, 2. add agents (each gets an API key, shown once), 3. give each agent a budget (a delegated grant).
// Everything goes through the same API calls the rest of the dashboard uses; amounts are typed in whole units and sent as integer minor units.
import { useEffect, useState } from "react";
import {
  createAgent, createMandate, delegateGrant, describeError, listAgents, money, toMinor,
  type MandateScope, type MyAgent,
} from "@/lib/api";
import Section, { Filler } from "@/components/ui/Section";
import { useSession } from "@/lib/session";

const words = (s: string) => s.split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
const inDays = (d: number) => new Date(Date.now() + d * 86_400_000).toISOString();

type Made = { mandateId: string; rootGrantId: string; total: number; reserve: number; categories: string[]; recipients: string[] };
type Given = { name: string; amount: number };

export default function SetupView() {
  const { session, signOut, setMandate } = useSession();
  const key = session!.key;
  // 1. mandate
  const [total, setTotal] = useState("1000");
  const [reserve, setReserve] = useState("100");
  const [days, setDays] = useState("30");
  const [recipients, setRecipients] = useState("aws, github, openai");
  const [categories, setCategories] = useState("cloud, tools");
  const [made, setMade] = useState<Made | null>(null);
  // 2. agents
  const [agentName, setAgentName] = useState("");
  const [agents, setAgents] = useState<MyAgent[]>([]);
  const [fresh, setFresh] = useState<{ name: string; key: string } | null>(null);
  const [copied, setCopied] = useState(false);
  // 3. budgets
  const [holder, setHolder] = useState("");
  const [amount, setAmount] = useState("300");
  const [perPayment, setPerPayment] = useState("100");
  const [approval, setApproval] = useState("60");
  const [grantDays, setGrantDays] = useState("14");
  const [given, setGiven] = useState<Given[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listAgents(key).then((r) => setAgents(r.agents)).catch(() => undefined);
  }, [key]);
  const chosen = agents.some((a) => a.principal_id === holder) ? holder : (agents[agents.length - 1]?.principal_id ?? "");

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setErr(null);
    try { await fn(); } catch (e) { setErr(describeError(e, "That did not work")); } finally { setBusy(false); }
  }

  const submitMandate = (e: React.FormEvent) => {
    e.preventDefault();
    const t = toMinor(total), r = toMinor(reserve), d = Number(days);
    if (t === null || t <= 0) return setErr("Enter the total as an amount, for example 1000 or 1000.50.");
    if (r === null || r >= t) return setErr("The protected reserve must be an amount below the total.");
    if (!Number.isInteger(d) || d < 1 || d > 365) return setErr("Valid for: enter a number of days from 1 to 365.");
    const rec = words(recipients), cat = words(categories);
    if (!rec.length || !cat.length) return setErr("List at least one recipient and one category, separated by commas.");
    const scope: MandateScope = { categories: cat, recipients: rec, per_tx_limit: t, can_delegate: true };
    void run(async () => {
      const m = await createMandate(key, { currency: "USD", total: t, protected_reserve: r, expires_at: inDays(d), scope });
      setMade({ mandateId: m.mandate_id, rootGrantId: m.root_grant_id, total: t, reserve: r, categories: cat, recipients: rec });
    });
  };

  const submitAgent = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const a = await createAgent(key, agentName.trim());
      setFresh({ name: a.name, key: a.api_key });
      setCopied(false);
      setAgentName("");
      setAgents((await listAgents(key)).agents);
    });
  };

  const submitGrant = (e: React.FormEvent) => {
    e.preventDefault();
    if (!made) return;
    const a = toMinor(amount), p = toMinor(perPayment), rv = approval.trim() === "" ? null : toMinor(approval), d = Number(grantDays);
    if (a === null || a <= 0) return setErr("Enter the budget as an amount, for example 300.");
    if (p === null || p <= 0) return setErr("Enter the limit for one payment as an amount, for example 100.");
    if (approval.trim() !== "" && rv === null) return setErr("The approval line must be an amount, or empty for none.");
    if (!Number.isInteger(d) || d < 1 || d > 365) return setErr("Valid for: enter a number of days from 1 to 365.");
    const who = agents.find((x) => x.principal_id === chosen);
    if (!who) return setErr("Add an agent first.");
    const scope: MandateScope = { categories: made.categories, recipients: made.recipients, per_tx_limit: p, can_delegate: false,
      ...(rv !== null ? { review_above: rv } : {}) };
    void run(async () => {
      await delegateGrant(key, { parent_grant_id: made.rootGrantId, holder_principal_id: who.principal_id, amount: a,
        expires_at: inDays(d), scope, idempotency_key: crypto.randomUUID() });
      setGiven((g) => [...g, { name: who.name, amount: a }]);
    });
  };

  async function copy() {
    if (!fresh) return;
    try { await navigator.clipboard.writeText(fresh.key); setCopied(true); } catch { setErr("Copy failed. Select the key and copy it by hand."); }
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><b className="fig">Budget Kernel</b><span>Set up your mandate</span></div>
        <div className="who">
          <span>{session?.name ?? ""}</span>
          <a href="#signout" onClick={(e) => { e.preventDefault(); signOut(); }}>Sign out</a>
        </div>
      </header>
      <nav className="tabs" aria-label="Setup"><a href="#setup" className="on" aria-current="page" onClick={(e) => e.preventDefault()}>Setup</a></nav>
      <main className="main">
        <Section span={6} title="1. Fund a mandate" meta={made ? "Done" : "The money agents may spend from"}>
          {made ? (
            <>
              <div className="row" style={{ gridTemplateColumns: "8rem minmax(0,1fr)" }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Total</span><b className="fig">{money(made.total)}</b></div>
              <div className="row" style={{ gridTemplateColumns: "8rem minmax(0,1fr)" }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Protected</span><span>{money(made.reserve)}, never spendable</span></div>
              <div className="row" style={{ gridTemplateColumns: "8rem minmax(0,1fr)" }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Recipients</span><span style={{ overflowWrap: "anywhere" }}>{made.recipients.join(", ")}</span></div>
              <div className="row" style={{ gridTemplateColumns: "8rem minmax(0,1fr)" }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Categories</span><span style={{ overflowWrap: "anywhere" }}>{made.categories.join(", ")}</span></div>
              <Filler>Next: add an agent on the right and give it a budget. You can open the dashboard at any time.</Filler>
            </>
          ) : (
            <form onSubmit={submitMandate} className="form">
              <label htmlFor="m-total">Total, in USD</label>
              <input id="m-total" className="field" inputMode="decimal" required value={total} onChange={(e) => setTotal(e.target.value)} />
              <label htmlFor="m-res">Protected reserve, in USD (held back, can never be spent)</label>
              <input id="m-res" className="field" inputMode="decimal" required value={reserve} onChange={(e) => setReserve(e.target.value)} />
              <label htmlFor="m-days">Valid for (days)</label>
              <input id="m-days" className="field" inputMode="numeric" required value={days} onChange={(e) => setDays(e.target.value)} />
              <label htmlFor="m-rec">Recipients agents may pay (separated by commas)</label>
              <input id="m-rec" className="field" required value={recipients} onChange={(e) => setRecipients(e.target.value)} />
              <label htmlFor="m-cat">Categories (separated by commas)</label>
              <input id="m-cat" className="field" required value={categories} onChange={(e) => setCategories(e.target.value)} />
              {err && !made && <p role="alert" className="alert">{err}</p>}
              <button disabled={busy} className="btn wide" style={{ marginTop: "1rem" }}>{busy ? "Creating…" : "Create the mandate"}</button>
            </form>
          )}
        </Section>

        <Section span={6} title="2. Add agents, give them a budget" meta={made ? `${agents.length} agent${agents.length === 1 ? "" : "s"}` : "Needs the mandate first"}
          foot={made ? <button className="linkbtn" onClick={() => setMandate(made.mandateId)}>Open the dashboard</button> : undefined}>
          {!made ? <Filler>Create the mandate first. Agents get their budget from it.</Filler> : (
            <>
              <form onSubmit={submitAgent}>
                <label htmlFor="a-name">New agent name</label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input id="a-name" className="field" required maxLength={100} value={agentName} onChange={(e) => setAgentName(e.target.value)} placeholder="Research bot" />
                  <button disabled={busy} className="btn small" style={{ height: "3rem", flex: "none" }}>Add agent</button>
                </div>
              </form>
              {fresh && (
                <div className="manage" role="status" style={{ marginTop: "1rem", paddingLeft: 0 }}>
                  <p style={{ margin: 0 }}><b>{fresh.name}</b> was added. Its API key is shown once. Copy it now: it cannot be shown again.</p>
                  <p className="serial" style={{ margin: "0.5rem 0", overflowWrap: "anywhere", userSelect: "all" }}>{fresh.key}</p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn ghost small" onClick={() => void copy()}>{copied ? "Copied" : "Copy the key"}</button>
                    <button className="btn ghost small" onClick={() => setFresh(null)}>I have stored it</button>
                  </div>
                </div>
              )}
              {agents.length > 0 && (
                <form onSubmit={submitGrant}>
                  <label htmlFor="g-agent">Give a budget to</label>
                  <select id="g-agent" className="field" value={chosen} onChange={(e) => setHolder(e.target.value)}>
                    {agents.map((a) => <option key={a.principal_id} value={a.principal_id}>{a.name}</option>)}
                  </select>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: "1rem" }}>
                    <div><label htmlFor="g-amt">Budget, in USD</label><input id="g-amt" className="field" inputMode="decimal" required value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
                    <div><label htmlFor="g-per">Most for one payment</label><input id="g-per" className="field" inputMode="decimal" required value={perPayment} onChange={(e) => setPerPayment(e.target.value)} /></div>
                    <div><label htmlFor="g-apr">Ask me above (empty: never)</label><input id="g-apr" className="field" inputMode="decimal" value={approval} onChange={(e) => setApproval(e.target.value)} /></div>
                    <div><label htmlFor="g-days">Valid for (days)</label><input id="g-days" className="field" inputMode="numeric" required value={grantDays} onChange={(e) => setGrantDays(e.target.value)} /></div>
                  </div>
                  <button disabled={busy} className="btn wide" style={{ marginTop: "1rem" }}>{busy ? "Working…" : "Give this agent a budget"}</button>
                </form>
              )}
              {err && made && <p role="alert" className="alert">{err}</p>}
              {given.map((g, i) => (
                <div key={i} className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}><b>{g.name}</b><span className="fig">{money(g.amount)}</span></div>
              ))}
              <Filler>{agents.length === 0 ? "Add your first agent above." : "Each agent can spend only within the budget and limits you give it."}</Filler>
            </>
          )}
        </Section>
      </main>
    </div>
  );
}
