"use client";
// Screen 3: free text -> POST /agent/request. Left: what the (untrusted) interpreter proposed.
// Right: what the deterministic kernel decided. Everything rendered here is plain text.
import { useState } from "react";
import { api, ApiError, money, type AgentResponse, type Interpretation, type Decision } from "@/lib/api";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

const STATE_TONE: Record<string, string> = {
  reserved: "text-ok",
  settled: "text-ok",
  proposed: "text-accent",
  rejected: "text-bad",
};

function Row({ k, v }: { k: string; v: string | number | null | undefined }) {
  if (v === null || v === undefined || v === "") return null;
  return (
    <div className="flex justify-between gap-3 text-sm">
      <dt className="text-muted">{k}</dt>
      <dd className="break-words text-right">{String(v)}</dd>
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
      <h4 className="mt-3 text-xs font-semibold uppercase text-muted">Route trail</h4>
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

function DecisionCard({ d, interp }: { d: Decision | null; interp: Interpretation }) {
  return (
    <div className="rounded-lg border border-line bg-card p-3">
      <h3 className="text-sm font-semibold">Kernel decision (authoritative)</h3>
      {d ? (
        <>
          <p className={`mt-2 text-xl font-semibold uppercase ${STATE_TONE[d.state] ?? ""}`}>{d.state}</p>
          <dl className="mt-2 flex flex-col gap-1">
            <Row k="Reason" v={d.reason} />
            <Row k="Review reason" v={d.review_reason} />
            <Row k="Replayed" v={d.replayed ? "yes (no second reservation)" : "no"} />
            <Row k="Transaction" v={d.transaction_id} />
          </dl>
          {d.state === "proposed" && (
            <p className="mt-2 text-sm text-muted">Held for the owner. No funds are reserved until approved.</p>
          )}
        </>
      ) : (
        <p className="mt-2 text-sm text-muted">
          The kernel was not called ({interp.status}). Nothing was reserved.
        </p>
      )}
    </div>
  );
}

export default function AskView() {
  const { session } = useSession();
  const { state, refresh } = useMandate();
  const grants = state?.grants.filter((g) => g.status === "active") ?? [];
  const [grantId, setGrantId] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<AgentResponse | null>(null);

  const chosen = grantId || grants[grants.length - 1]?.id || "";

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
      setErr(e instanceof ApiError ? `${e.code}: ${e.message}` : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      {state && grants.length === 0 && (
        <p role="status" className="rounded-md border border-line bg-card px-3 py-2 text-sm text-muted">
          No active grant in this mandate, so there is nothing to ask against.
        </p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Grant
          <select value={chosen} onChange={(e) => setGrantId(e.target.value)} className="field">
            {grants.map((g) => (
              <option key={g.id} value={g.id}>
                {g.id.slice(0, 8)} · available {money(g.available, state?.mandate.currency)}
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
        <button disabled={busy || !chosen} className="btn-primary">{busy ? "Asking…" : "Send request"}</button>
      </form>
      {err && <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{err}</p>}
      {result && (
        <div className="grid gap-3 md:grid-cols-2">
          <InterpretationCard i={result.interpretation} />
          <DecisionCard d={result.decision} interp={result.interpretation} />
        </div>
      )}
    </section>
  );
}
