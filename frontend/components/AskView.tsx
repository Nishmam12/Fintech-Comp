"use client";
// Screen 3: free text -> POST /agent/request. The kernel's decision comes first, in plain words.
// What the (untrusted) interpreter proposed sits in a collapsed section below. Everything rendered here is plain text.
import { useState } from "react";
import {
  api, describeError, grantName, money, reasonText, reasonTitle,
  type AgentResponse, type Interpretation, type Decision,
} from "@/lib/api";
import Section from "@/components/ui/Section";
import Stamp, { type Tone } from "@/components/ui/Stamp";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

// One-tap requests that fill the text box. The outcomes hold for the demo mandate's Research bot grant
// (scripts/demo_seed.py: 100.00 per payment, owner approval above 60.00, recipients aws/github/openai).
const EXAMPLES = [
  { text: "pay 20 USD to aws for cloud", outcome: "approved" },
  { text: "pay 80 USD to aws for cloud", outcome: "held for approval" },
  { text: "pay 150 USD to aws for cloud", outcome: "over the limit" },
  // Not on the grant's list, so the rules path cannot read it and the model is asked; it fails closed (review B2).
  { text: "pay 10 USD to evil for cloud", outcome: "unknown recipient: not sent" },
];

function Row({ k, v }: { k: string; v: string | number | null | undefined }) {
  if (v === null || v === undefined || v === "") return null;
  return (
    <div className="flex justify-between gap-3 text-sm">
      <dt className="text-muted">{k}</dt>
      <dd className="wrap-anywhere text-right">{String(v)}</dd>
    </div>
  );
}

function InterpretationCard({ i }: { i: Interpretation }) {
  const p = i.proposal;
  return (
    <div className="rounded-lg border border-line bg-card p-3">
      <h3 className="text-sm font-semibold">Interpretation (untrusted proposal)</h3>
      <dl className="mt-2 flex flex-col gap-1">
        <Row k="Status" v={i.status} />
        <Row k="Reasons" v={i.reasons.join(", ")} />
        {p && (
          <>
            <Row k="Type" v={p.request_type} />
            <Row k="Amount" v={p.amount_minor !== null ? money(p.amount_minor, p.currency ?? "") : null} />
            <Row k="Recipient" v={p.recipient} />
            <Row k="Category" v={p.category} />
            <Row k="Purpose" v={p.purpose} />
            <Row k="Missing" v={p.missing_fields.join(", ")} />
            <Row k="Ambiguities" v={p.ambiguities.join("; ")} />
            <Row k="Conflicts" v={p.conflicts.join("; ")} />
          </>
        )}
      </dl>
      {p?.explanation && <p className="mt-2 text-sm text-muted">{p.explanation}</p>}
      {p && p.evidence.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 text-sm">
          {p.evidence.map((e, n) => (
            <li key={n} className="text-muted">
              {e.field}: <span className="text-foreground">“{e.quote}”</span>
            </li>
          ))}
        </ul>
      )}
      <h4 className="mt-3 text-sm font-semibold text-muted">Route trail</h4>
      <ol className="mt-1 flex flex-col gap-1 text-sm">
        {i.trail.length === 0 && <li className="text-muted">No steps recorded.</li>}
        {i.trail.map((t, n) => (
          <li key={n} className="rounded border border-line px-2 py-1">
            <span className="font-medium">{t.step}</span>
            {t.outcome && <span> · {t.outcome}</span>}
            {t.provider && <span className="text-muted"> · {t.provider}</span>}
            {t.model_id && <span className="text-muted"> · {t.model_id}</span>}
            {t.cost_micro !== undefined && <span className="text-muted"> · {t.cost_micro} micro-USD</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

// Why the interpreter could not hand the kernel a request. Unknown codes are shown unchanged.
const INTERPRETER_TEXT: Record<string, string> = {
  PROVIDER_FAILED: "the AI model could not be reached",
  ROUTE_UNAVAILABLE: "no AI model is available",
  NO_FAST_PATH_MATCH: "the wording did not match a simple pattern",
  BUDGET_EXHAUSTED: "the AI model budget is used up",
  AGENT_BUDGET_EXHAUSTED: "this agent's AI model budget is used up",
  BAD_INPUT_SIZE: "the request is empty or too long",
};

// The kernel's verdict as a stamp and one plain sentence, derived only from its answer.
const sentence = (t: string) => (/[.!?]$/.test(t.trim()) ? t.trim() : `${t.trim()}.`);
function verdict(d: Decision | null, interp: Interpretation): { stamp: string; tone: Tone; text: string; after: string } {
  if (!d) {
    const why = interp.reasons.map((r) => INTERPRETER_TEXT[r] ?? r).join(", ");
    return { stamp: "Not sent", tone: "dim", text: `${why ? `${why[0].toUpperCase()}${why.slice(1)}. ` : ""}The request could not be read well enough to send.`, after: "Nothing was reserved." };
  }
  if (d.state === "proposed") {
    return { stamp: "Held", tone: "wait", text: `${d.review_reason ? `${sentence(reasonText(d.review_reason))} ` : ""}The owner has to approve it.`, after: "No money is reserved until the owner approves." };
  }
  if (d.state === "rejected") {
    return {
      stamp: "Refused", tone: "no", text: d.reason ? sentence(reasonText(d.reason)) : "The kernel said no.",
      after: d.suspended ? "Nothing was reserved. This refusal suspended the grant until the owner reinstates it." : "Nothing was reserved. Repeated refusals suspend the grant until the owner reinstates it.",
    };
  }
  if (d.state === "settled") return { stamp: "Paid", tone: "ok", text: "Approved and paid.", after: "The payment settled." };
  return { stamp: "Approved", tone: "ok", text: "Approved and the money is reserved.", after: "The reservation holds until the payment settles or expires." };
}

export default function AskView() {
  const { session } = useSession();
  const { state, refresh } = useMandate();
  // Only the holder can spend from a grant (the server enforces it), so only the caller's own active grants are offered.
  const grants = state?.grants.filter((g) => g.status === "active" && g.holder_principal_id === session?.principalId) ?? [];
  const [grantId, setGrantId] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<AgentResponse | null>(null);

  const chosen = grants.some((g) => g.id === grantId) ? grantId : (grants[grants.length - 1]?.id ?? "");
  const cur = state?.mandate.currency ?? "USD";
  const chosenGrant = grants.find((g) => g.id === chosen);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !chosen) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await api<AgentResponse>(session.key, "/agent/request", {
        method: "POST",
        body: { grant_id: chosen, text, idempotency_key: crypto.randomUUID() },
      });
      setResult(r);
      refresh();
    } catch (e) {
      setResult(null);
      setErr(describeError(e, "Request failed"));
    } finally {
      setBusy(false);
    }
  }

  const p = result?.interpretation.proposal;
  const v = result ? verdict(result.decision, result.interpretation) : null;

  return (
    <>
      <Section span={6} title="Ask to pay" meta={chosenGrant ? `${money(chosenGrant.available, cur)} free` : undefined}>
        <form onSubmit={submit} className="form">
          {state && grants.length === 0 && (
            <p role="status" className="alert" style={{ borderColor: "var(--rule)", color: "var(--ink-2)" }}>
              You do not hold an active grant in this mandate, so there is nothing to ask against.
            </p>
          )}
          <label htmlFor="ask-grant">Spend from</label>
          <select id="ask-grant" value={chosen} onChange={(e) => setGrantId(e.target.value)} className="field">
            {grants.map((g) => <option key={g.id} value={g.id}>{grantName(g)}, {money(g.available, cur)} free</option>)}
          </select>
          <label htmlFor="ask-text">Request, in your own words</label>
          <textarea id="ask-text" required maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} placeholder="pay 50 USD to aws for cloud" className="field" />
          <label style={{ margin: "1rem 0 0" }}>Or try an example</label>
          <div className="chips">
            {EXAMPLES.map((x) => (
              <button key={x.text} type="button" className="chip" onClick={() => setText(x.text)}>{x.text}<span>{x.outcome}</span></button>
            ))}
          </div>
          <button disabled={busy || !chosen} className="btn wide">{busy ? "Asking the kernel…" : "Send to the kernel"}</button>
        </form>
      </Section>

      <Section span={6} title="Decision" meta="Untrusted proposal, authoritative verdict" live>
        {err && <p role="alert" className="alert">{err}</p>}
        <div className="pair">
          {result ? (
            <div className="slip proposal">
              <small>The model read it as</small>
              <span>
                {p && p.amount_minor !== null
                  ? <>Pay <b>{money(p.amount_minor, p.currency ?? cur)}</b> to <b>{p.recipient ?? "?"}</b>, category <b>{p.category ?? "?"}</b></>
                  : "Nothing it could turn into a payment"}
              </span>
              <small>Untrusted. The model only proposes.</small>
            </div>
          ) : (
            <div className="slip proposal"><small>The model read it as</small><span>{busy ? "Reading your request…" : "Nothing asked yet"}</span></div>
          )}
          <div className="arrow" aria-hidden="true">↓</div>
          {v ? (
            <div className={`slip verdict ${v.tone}`} title={result?.decision?.reason ? reasonTitle(result.decision.reason) : undefined}>
              <Stamp>{v.stamp}</Stamp><p>{v.text}</p>
            </div>
          ) : (
            <div className="slip proposal"><small>The kernel decides</small><span>{busy ? "Asking the kernel…" : "Send a request to see the verdict"}</span></div>
          )}
        </div>
        <p className="consequence">
          {v ? v.after : "The model only reads the request. The kernel checks it against the grant's limits before any money moves."}
          {result?.decision?.replayed && " This exact request was already decided; nothing new was reserved."}
        </p>
        {result && (
          <details className="manage" style={{ padding: "0.75rem 0" }}>
            <summary style={{ cursor: "pointer" }}>How the model read this request</summary>
            <div style={{ marginTop: "0.75rem" }}><InterpretationCard i={result.interpretation} /></div>
          </details>
        )}
      </Section>
    </>
  );
}
