"use client";
// Screen 3: free text -> POST /agent/request. The kernel's decision comes first, in plain words.
// What the (untrusted) interpreter proposed sits in a collapsed section below. Everything rendered here is plain text.
import { useState } from "react";
import {
  api, describeError, grantName, money, reasonText, reasonTitle, txState,
  type AgentResponse, type Interpretation, type Decision,
} from "@/lib/api";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

// One-tap requests that fill the text box. The outcomes hold for the demo mandate's Research bot grant
// (scripts/demo_seed.py: 100.00 per payment, owner approval above 60.00, recipients aws/github/openai).
const EXAMPLES = [
  { text: "pay 20 USD to aws for cloud", outcome: "approved" },
  { text: "pay 80 USD to aws for cloud", outcome: "held for approval" },
  { text: "pay 150 USD to aws for cloud", outcome: "over the limit" },
  { text: "pay 10 USD to evil for cloud", outcome: "wrong recipient" },
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

// The decision in plain words, derived only from the kernel's answer.
function headline(d: Decision | null): string {
  if (!d) return "Not sent to the kernel";
  if (d.state === "proposed") return "Held for the owner's approval";
  if (d.state === "rejected") return `Refused: ${d.reason ? reasonText(d.reason) : "the kernel said no."}`;
  if (d.state === "settled") return "Approved and paid";
  return "Approved and reserved";
}

function DecisionCard({ d, interp }: { d: Decision | null; interp: Interpretation }) {
  const st = txState(d?.state ?? "");
  return (
    <div className="panel p-5 lg:p-6">
      <p className="text-sm text-muted">Kernel decision</p>
      <p
        className={`fig mt-1 text-2xl lg:text-3xl ${st.tone}`}
        title={d?.reason ? reasonTitle(d.reason) : undefined}
      >
        {headline(d)}
      </p>
      {d ? (
        <>
          {d.state === "proposed" && (
            <p className="mt-2 text-sm text-muted">
              {d.review_reason ? `${reasonText(d.review_reason)} ` : ""}No money is reserved until the owner approves.
            </p>
          )}
          {d.suspended && <p className="mt-2 text-sm text-warn">This refusal suspended the grant (circuit breaker).</p>}
          {d.replayed && <p className="mt-2 text-sm text-muted">This exact request was already decided; nothing new was reserved.</p>}
        </>
      ) : (
        <p className="mt-2 text-sm text-muted">
          {interp.reasons.length > 0 ? `${interp.reasons.map((r) => INTERPRETER_TEXT[r] ?? r).join(", ")}. ` : ""}The request could not be read well enough to send. Nothing was reserved.
        </p>
      )}
    </div>
  );
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

  return (
    <section className="flex max-w-2xl flex-col gap-4">
      <div aria-live="polite" className="flex flex-col gap-3">
        {result ? (
          <DecisionCard d={result.decision} interp={result.interpretation} />
        ) : (
          <div className="panel p-5 lg:p-6">
            <p className="text-sm text-muted">Kernel decision</p>
            <p className="fig mt-1 text-2xl text-muted lg:text-3xl">{busy ? "Asking the kernel…" : "Nothing asked yet"}</p>
          </div>
        )}
        {err && <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{err}</p>}
      </div>

      {state && grants.length === 0 && (
        <p role="status" className="rounded-md border border-line bg-card px-3 py-2 text-sm text-muted">
          You do not hold an active grant in this mandate, so there is nothing to ask against.
        </p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Spend from
          <select value={chosen} onChange={(e) => setGrantId(e.target.value)} className="field">
            {grants.map((g) => (
              <option key={g.id} value={g.id}>
                {grantName(g)} · {money(g.available, state?.mandate.currency)} available
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Request
          <textarea
            required
            maxLength={2000}
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="pay 50 USD to aws for cloud"
            className="field"
          />
        </label>
        <div>
          <p className="text-sm text-muted">Try an example</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {EXAMPLES.map((x) => (
              <li key={x.text}>
                <button type="button" onClick={() => setText(x.text)} className="btn-ghost text-left">
                  {x.text}
                  <span className="block text-xs font-normal text-muted">{x.outcome}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <button disabled={busy || !chosen} className="btn-primary">{busy ? "Asking…" : "Send request"}</button>
      </form>

      {result && (
        <details className="panel p-4">
          <summary className="cursor-pointer text-sm font-semibold">How the model read this request</summary>
          <p className="mt-1 text-xs text-muted">Untrusted: the model only proposes. The kernel decision above is the authority.</p>
          <div className="mt-3">
            <InterpretationCard i={result.interpretation} />
          </div>
        </details>
      )}
    </section>
  );
}
