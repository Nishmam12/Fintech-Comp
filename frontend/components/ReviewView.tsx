"use client";
// Screen 4 / BK-322 on the revision 3 system: the owner's approval inbox. Left: held requests as cheques awaiting
// signature, then what was already decided today. Right: "Approval rules" (counters and each grant's threshold).
// Held ("proposed") transactions hold no funds until approved. Approving re-runs every kernel check, so an approval
// can still come back refused; that result is shown as-is.
import { useEffect, useState } from "react";
import { api, describeError, grantName, money, reasonText, reasonTitle, type Transaction } from "@/lib/api";
import Section, { Filler } from "@/components/ui/Section";
import Stamp from "@/components/ui/Stamp";
import { useToast } from "@/components/Toast";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

const POLL_MS = 3000;
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const isToday = (iso: string) => new Date(iso).toDateString() === new Date().toDateString();
// money() gives "80.00 USD"; the cheque shows the figure large and the currency small.
const figure = (minor: number, cur: string) => money(minor, cur).replace(/\s+\S+$/, "");

export const native = true;

export default function ReviewView() {
  const { session } = useSession();
  const { state, refresh } = useMandate();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    const id = setInterval(() => { if (document.visibilityState === "visible") refresh(); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  if (!state || !session) return <Section span={12} title="Review"><p className="tag" style={{ padding: "1rem 0" }}>Loading…</p></Section>;
  const held = state.transactions.filter((t) => t.state === "proposed");
  const cur = state.mandate.currency;
  const isOwner = state.mandate.owner_principal_id === session.principalId;

  const holderOf = (t: Transaction) => {
    const g = state.grants.find((x) => x.id === t.grant_id);
    return g ? grantName(g) : `Grant ${t.grant_id.slice(0, 8)}`;
  };

  // Decided today: everything that is no longer waiting (the API returns newest first).
  const decided = state.transactions.filter((t) => t.state !== "proposed" && isToday(t.created_at));
  const approved = decided.filter((t) => ["approved", "submitted", "settled"].includes(t.state)).length;
  const denied = decided.filter((t) => t.reject_reason === "DENIED_BY_REVIEWER").length;
  const rules = state.grants.filter((g) => g.parent_id !== null && g.status !== "revoked");

  async function decide(t: Transaction, approve: boolean) {
    setBusyId(t.id);
    setNotice(null);
    try {
      const r = await api<{ state: string; reason?: string | null }>(session!.key, `/transactions/${t.id}/review`, {
        method: "POST",
        body: { approve },
      });
      if (r.state === "rejected" && approve) {
        // Approving re-runs every check, so the kernel can still refuse; say so plainly instead of claiming success.
        setNotice(`Not approved. ${r.reason ? reasonText(r.reason) : "The kernel refused it."}`);
      } else {
        toast(approve ? "Request approved" : "Request denied");
      }
    } catch (e) {
      setNotice(describeError(e, "Review failed"));
    } finally {
      setBusyId(null);
      refresh();
    }
  }

  return (
    <>
      <Section
        span={8}
        title="Waiting for you"
        meta={`${held.length} request${held.length === 1 ? "" : "s"}, refreshes every 3 s`}
        live
      >
        {notice && <p role="status" className="alert">{notice}</p>}
        {held.map((t) => (
          <div key={t.id} className="held-cheque">
            <div style={{ minWidth: 0 }}>
              <p style={{ margin: 0, color: "var(--ink-2)", overflowWrap: "anywhere" }}>{holderOf(t)} asks to pay</p>
              <div className="amount fig">{figure(t.amount, t.currency || cur)}<small>{t.currency || cur}</small></div>
              <p style={{ margin: "0.25rem 0 0", overflowWrap: "anywhere" }}>
                to <b>{t.recipient}</b> for <b>{t.category}</b>, requested {hhmm(t.created_at)}
              </p>
              <p className="wait" style={{ margin: "0.5rem 0 0" }} title={t.review_reason ? reasonTitle(t.review_reason) : undefined}>
                {t.review_reason ? `Held because: ${reasonText(t.review_reason)}` : "Held for your approval."}
              </p>
              {t.proposal && (
                <details style={{ marginTop: "0.5rem", fontSize: "0.875rem", border: "1.5px dashed var(--muted)", padding: "0.5rem 0.75rem" }}>
                  <summary style={{ cursor: "pointer", color: "var(--ink-2)" }}>Model proposal (untrusted)</summary>
                  <p style={{ margin: "0.5rem 0 0", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{t.proposal.explanation}</p>
                  {t.proposal.purpose && <p className="tag" style={{ margin: "0.25rem 0 0", overflowWrap: "anywhere" }}>Purpose: {t.proposal.purpose}</p>}
                  {t.proposal.evidence?.length > 0 && (
                    <ul className="tag" style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                      {t.proposal.evidence.map((e, i) => <li key={i} style={{ overflowWrap: "anywhere" }}>{e.field}: &ldquo;{e.quote}&rdquo;</li>)}
                    </ul>
                  )}
                  {[...(t.proposal.ambiguities ?? []), ...(t.proposal.conflicts ?? [])].map((x, i) => (
                    <p key={i} className="tag" style={{ margin: "0.25rem 0 0", overflowWrap: "anywhere" }}>{x}</p>
                  ))}
                </details>
              )}
            </div>
            {isOwner ? (
              <div className="actions">
                <button className="btn" disabled={busyId === t.id} onClick={() => void decide(t, true)}>Approve</button>
                <button className="btn ghost" disabled={busyId === t.id} onClick={() => void decide(t, false)}>Deny</button>
              </div>
            ) : (
              <p className="tag" style={{ margin: 0 }}>Waiting for the mandate owner. Only the owner can approve or deny.</p>
            )}
          </div>
        ))}
        {held.length === 0 && (
          <div className="row"><span className="dim">Nothing is waiting for you. Requests above an agent&rsquo;s approval limit appear here.</span></div>
        )}
        <div className="day">Decided today</div>
        {decided.slice(0, 20).map((t) => {
          const refused = t.state === "rejected";
          const released = t.state === "released";
          const stamp = refused ? (t.reject_reason === "DENIED_BY_REVIEWER" ? "Denied" : "Refused") : released ? "Released" : "Approved";
          const tone = refused ? "no" : released ? "dim" : "ok";
          const why = refused ? (t.reject_reason ? reasonText(t.reject_reason) : "The kernel said no") : released ? "The reservation was released" : "Money reserved for this payment";
          return (
            <div key={t.id} className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }} title={why}>
              <div className="name">
                <b>Pay {figure(t.amount, t.currency || cur)} to {t.recipient}, {t.category}</b>
                <em style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{holderOf(t)}, {hhmm(t.created_at)}. {why}</em>
              </div>
              <span className={tone}><Stamp>{stamp}</Stamp></span>
            </div>
          );
        })}
        <Filler>Requests above an agent&rsquo;s approval limit wait here until you approve or deny them. Nothing is reserved while they wait.</Filler>
      </Section>

      <Section
        span={4}
        title="Approval rules"
        meta="Today"
        head={
          <div className="cells">
            <div className="cell"><b className="fig wait">{held.length}</b><span>Waiting</span></div>
            <div className="cell"><b className="fig ok">{approved}</b><span>Approved</span></div>
            <div className="cell"><b className="fig">{denied}</b><span>Denied</span></div>
          </div>
        }
      >
        {rules.map((g) => (
          <div key={g.id} className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
            <div className="name"><b>{grantName(g)}</b><em>Approval above</em></div>
            {g.scope.review_above !== undefined
              ? <span className="num fig">{figure(g.scope.review_above, cur)}</span>
              : <span className="num dim">none set</span>}
          </div>
        ))}
        <Filler />
        <p className="explain">
          Approving re-runs every check. If the grant has changed since the request (lower funds, suspended, revoked), the kernel can still refuse.
        </p>
      </Section>
    </>
  );
}
