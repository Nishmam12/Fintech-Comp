"use client";
// BK-413 circuit breaker controls (ADR-0009 B). Suspend freezes a grant and everything below it; reinstate lifts it.
// Suspend: the mandate owner and holders of a grant above this one. Reinstate: the MANDATE OWNER ONLY (ADR-0009 K1);
// an ancestor holder who sees a suspended grant gets an explanation instead of a button. The server enforces both rules.
// The kill switch (RevokeControl) is separate and unchanged.
import { useState } from "react";
import { api, describeError, type Grant } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

export default function SuspendControl({ g, canManage, isOwner }: { g: Grant; canManage: boolean; isOwner: boolean }) {
  const { session } = useSession();
  const { refresh } = useMandate();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const suspended = g.status === "suspended";

  // Anyone who is not the owner (the holder itself or an ancestor holder) is told who can reinstate; only the owner gets the button.
  if (suspended && !isOwner) {
    return <p role="status" className="tag" style={{ margin: "0.75rem 0 0", fontSize: "0.875rem" }}>Suspended. Only the mandate owner can reinstate this grant.</p>;
  }
  if (!canManage || (g.status !== "active" && !suspended)) return null;

  async function run() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    try {
      await api(session.key, `/grants/${g.id}/${suspended ? "reinstate" : "suspend"}`, { method: "POST", body: {} });
      setConfirming(false);
      toast(suspended ? "Grant reinstated" : "Grant suspended");
      refresh();
    } catch (e) {
      setErr(describeError(e, suspended ? "Reinstate failed" : "Suspend failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      {err && <p role="alert" className="alert">{err}</p>}
      {!confirming ? (
        <button onClick={() => setConfirming(true)} className="btn ghost small wide">
          {suspended ? "Reinstate this grant" : "Suspend this grant"}
        </button>
      ) : (
        <div style={{ border: "1px solid var(--rule)", background: "var(--paper)", padding: "0.75rem" }}>
          <p style={{ margin: 0 }}>
            {suspended
              ? "The holder can spend again. The strike count starts from zero."
              : "The holder and every grant below it cannot spend until you reinstate. Reservations already made are not released early, and transfers in flight continue."}
          </p>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button disabled={busy} onClick={() => void run()} className="btn small">
              {busy ? "Working…" : suspended ? "Confirm reinstate" : "Confirm suspend"}
            </button>
            <button disabled={busy} onClick={() => setConfirming(false)} className="btn ghost small">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
