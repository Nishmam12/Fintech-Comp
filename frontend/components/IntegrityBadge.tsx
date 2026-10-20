"use client";
// BK-413: tamper-evidence seal (ADR-0009 A4). Owner only. Everything shown is what GET /integrity returned;
// when the call fails the seal says so and never guesses. The explorer link is the API's, never built here.
// Rendered inside the mandate cheque as its right-hand cell.
import { useEffect, useState } from "react";
import { ApiError, describeError, getIntegrity, type Integrity } from "@/lib/api";
import Seal from "@/components/ui/Seal";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

export default function IntegrityBadge({ ledgerOk = true }: { ledgerOk?: boolean }) {
  const { session } = useSession();
  const { state } = useMandate();
  const [data, setData] = useState<Integrity | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const isOwner = !!session && !!state && state.mandate.owner_principal_id === session.principalId;
  // Re-verify when the visible history changes (the transactions list grows with every decision).
  const stamp = state ? `${state.transactions.length}:${state.transactions[0]?.id ?? ""}:${state.grants.length}` : "";

  useEffect(() => {
    if (!session || !isOwner) return;
    let live = true;
    if (!session.mandateId) return;
    getIntegrity(session.key, session.mandateId)
      .then((r) => { if (live) { setData(r); setErr(null); } })
      .catch((e) => {
        if (!live) return;
        setData(null);
        setErr(e instanceof ApiError && e.status === 404 ? "Not available on this server yet." : describeError(e, "Not available."));
      });
    return () => { live = false; };
  }, [session, isOwner, stamp]);

  if (!isOwner) return null;
  const cell = (seal: React.ReactNode, title: string, line: string, extra?: React.ReactNode) => (
    <div className="c4 seal-cell" role="status">
      <div className="seal-line">{seal}<p><b>{title}</b>{line}</p></div>
      {extra}
    </div>
  );
  if (err) return cell(<Seal ok={false} />, "History check unavailable", err);
  if (!data) return cell(<div className="seal skel" aria-hidden />, "Checking history", "Recomputing the hash chain");

  const a = data.last_anchor;
  const link = a?.explorer_url?.startsWith("https://") ? a.explorer_url : null;
  if (!data.ok) {
    return cell(<Seal ok={false} />, `History BROKEN${data.broken_at !== null ? ` at record ${data.broken_at}` : ""}`, `Reason: ${data.reason ?? "unknown"}`);
  }
  const anchorLine = a ? `Last anchor: record ${a.seq}, ${a.status}${a.matches ? ", matches" : ", DOES NOT MATCH"}` : "Not anchored on-chain yet.";
  return cell(
    <Seal ok={ledgerOk} />,
    "History intact",
    `${data.length} records, ${ledgerOk ? "ledger checks pass" : "LEDGER CHECK FAILED"}`,
    link ? <a href={link} target="_blank" rel="noopener noreferrer">{anchorLine}, view on Base Sepolia</a> : <p>{anchorLine}</p>,
  );
}
