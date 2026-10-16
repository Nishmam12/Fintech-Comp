"use client";
// BK-413 circuit breaker controls (ADR-0009 B). Suspend freezes a grant and everything below it; reinstate lifts it.
// Shown to the mandate owner and to holders of a grant above this one; the server enforces the same rule.
// The kill switch (RevokeControl) is separate and unchanged.
import { useState } from "react";
import { api, describeError, type Grant } from "@/lib/api";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

export default function SuspendControl({ g, canManage }: { g: Grant; canManage: boolean }) {
  const { session } = useSession();
  const { refresh } = useMandate();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const suspended = g.status === "suspended";

  if (!canManage || (g.status !== "active" && !suspended)) return null;

  async function run() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    try {
      await api(session.key, `/grants/${g.id}/${suspended ? "reinstate" : "suspend"}`, { method: "POST", body: {} });
      setConfirming(false);
      refresh();
    } catch (e) {
      setErr(describeError(e, suspended ? "Reinstate failed" : "Suspend failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      {err && <p role="alert" className="mb-2 text-sm text-bad">{err}</p>}
      {!confirming ? (
        <button onClick={() => setConfirming(true)} className="btn-ghost w-full">
          {suspended ? "Reinstate this grant" : "Suspend this grant"}
        </button>
      ) : (
        <div className="rounded-md border border-line bg-background p-3">
          <p className="text-sm">
            {suspended
              ? "The holder can spend again. The strike count starts from zero."
              : "The holder and every grant below it cannot spend until you reinstate. Reservations already made are not released early, and transfers in flight continue."}
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button disabled={busy} onClick={() => void run()} className="btn-primary">
              {busy ? "Working…" : suspended ? "Confirm reinstate" : "Confirm suspend"}
            </button>
            <button disabled={busy} onClick={() => setConfirming(false)} className="btn-ghost min-h-12">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
