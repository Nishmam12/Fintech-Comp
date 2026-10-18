"use client";
// BK-413: tamper-evidence badge (ADR-0009 A4). Owner only. Everything shown is what GET /integrity returned;
// when the call fails the badge says so and never guesses. The explorer link is the API's, never built here.
import { useEffect, useState } from "react";
import { ApiError, describeError, getIntegrity, type Integrity } from "@/lib/api";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

export default function IntegrityBadge() {
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
  if (err) {
    return (
      <div role="status" className="rounded-lg border border-line bg-card px-4 py-3">
        <p className="text-base font-semibold">History check unavailable</p>
        <p className="text-sm text-muted">{err}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div role="status" aria-label="Checking history" className="panel animate-pulse px-4 py-3">
        <div className="h-4 w-2/5 rounded bg-line" />
        <div className="mt-2 h-3 w-full rounded bg-line" />
        <div className="mt-1.5 h-3 w-3/4 rounded bg-line" />
      </div>
    );
  }

  const a = data.last_anchor;
  const link = a?.explorer_url?.startsWith("https://") ? a.explorer_url : null;
  return (
    <div
      role="status"
      className={`rounded-lg border px-4 py-3 ${data.ok ? "border-ok/40 bg-ok/10 text-ok" : "border-bad/40 bg-bad/10 text-bad"}`}
    >
      {data.ok ? (
        <>
          <p className="text-base font-semibold">History intact · {data.length} records</p>
          <p className="text-sm opacity-80">Every record is linked to the one before it, so editing any record breaks the chain.</p>
          <p className="mt-1 text-xs opacity-80">
            Latest link <span className="font-mono">{data.head_hash.slice(0, 12)}</span> (record {data.head_seq}), recomputed by the server.
          </p>
        </>
      ) : (
        <>
          <p className="text-base font-semibold">History BROKEN{data.broken_at !== null ? ` at record ${data.broken_at}` : ""}</p>
          <p className="text-sm">Reason: <span className="font-mono">{data.reason ?? "unknown"}</span></p>
        </>
      )}
      <p className="mt-1 text-sm opacity-80">
        {a ? (
          <>
            Last on-chain anchor: record {a.seq}, {a.status}
            {a.matches ? ", matches" : ", DOES NOT MATCH"}
          </>
        ) : (
          "Not anchored on-chain yet."
        )}
      </p>
      {link && (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-ghost mt-3 inline-flex items-center text-foreground"
        >
          View anchor on Base Sepolia
        </a>
      )}
    </div>
  );
}
