"use client";
// Screen 4 / BK-322: the owner's approval inbox. Held ("proposed") transactions hold no funds until approved.
// Approving re-runs every kernel check, so an approval can still come back refused; that result is shown as-is.
import { useEffect, useState } from "react";
import { api, describeError, money, type Transaction } from "@/lib/api";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

const POLL_MS = 3000;

export default function ReviewView() {
  const { session } = useSession();
  const { state, refresh } = useMandate();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const id = setInterval(() => { if (document.visibilityState === "visible") refresh(); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  if (!state || !session) return <p className="p-4 text-sm text-muted">Loading…</p>;
  const held = state.transactions.filter((t) => t.state === "proposed");
  const cur = state.mandate.currency;
  const isOwner = state.mandate.owner_principal_id === session.principalId;

  async function decide(t: Transaction, approve: boolean) {
    setBusyId(t.id);
    setNotice(null);
    try {
      const r = await api<{ state: string; reason?: string | null }>(session!.key, `/transactions/${t.id}/review`, {
        method: "POST",
        body: { approve },
      });
      setNotice({ ok: true, text: `${approve ? "Approve" : "Deny"} → ${r.state}${r.reason ? ` (${r.reason})` : ""}` });
    } catch (e) {
      setNotice({ ok: false, text: describeError(e, "Review failed") });
    } finally {
      setBusyId(null);
      refresh();
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <p className="text-xs text-muted">Refreshes every 3 seconds. Held requests reserve no funds until you approve.</p>
      {notice && (
        <p role="status" className={`rounded-md border px-3 py-2 text-sm ${notice.ok ? "border-ok/40 bg-ok/10 text-ok" : "border-bad/40 bg-bad/10 text-bad"}`}>
          {notice.text}
        </p>
      )}
      {held.length === 0 && <p className="rounded-lg border border-line bg-card p-4 text-sm text-muted">Nothing is waiting for review.</p>}
      <ul className="flex flex-col gap-3">
        {held.map((t) => (
          <li key={t.id} className="rounded-lg border border-line bg-card p-3">
            <p className="text-xl font-semibold">{money(t.amount, t.currency || cur)}</p>
            <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted">To</dt><dd className="wrap-anywhere text-right">{t.recipient}</dd>
              <dt className="text-muted">Category</dt><dd className="wrap-anywhere text-right">{t.category}</dd>
              <dt className="text-muted">Why held</dt><dd className="wrap-anywhere text-right">{t.review_reason ?? "—"}</dd>
              <dt className="text-muted">Grant</dt><dd className="text-right font-mono text-xs">{t.grant_id.slice(0, 8)}</dd>
              <dt className="text-muted">Requested</dt><dd className="text-right">{new Date(t.created_at).toLocaleString()}</dd>
            </dl>
            {t.proposal && (
              <details className="mt-2 rounded-md border border-line p-2 text-sm">
                <summary className="cursor-pointer text-muted">Model proposal (untrusted)</summary>
                <p className="mt-1 wrap-anywhere whitespace-pre-wrap">{t.proposal.explanation}</p>
                {t.proposal.purpose && <p className="mt-1 wrap-anywhere text-muted">Purpose: {t.proposal.purpose}</p>}
                {t.proposal.evidence?.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-xs text-muted">
                    {t.proposal.evidence.map((e, i) => (
                      <li key={i} className="wrap-anywhere">{e.field}: &ldquo;{e.quote}&rdquo;</li>
                    ))}
                  </ul>
                )}
                {[...(t.proposal.ambiguities ?? []), ...(t.proposal.conflicts ?? [])].map((x, i) => (
                  <p key={i} className="mt-1 wrap-anywhere text-xs text-muted">{x}</p>
                ))}
              </details>
            )}
            {isOwner ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button disabled={busyId === t.id} onClick={() => void decide(t, true)} className="btn-primary">Approve</button>
                <button disabled={busyId === t.id} onClick={() => void decide(t, false)} className="btn-ghost min-h-12">Deny</button>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">Waiting for the mandate owner. Only the owner can approve or deny.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
