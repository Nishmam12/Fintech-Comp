"use client";
// BK-323 kill switch: revoke one grant (and everything below it) with a confirmation step.
// The result is shown exactly as the API returns it. In-flight transfers cannot be recalled, so they are
// reported separately and never described as reclaimed.
import { useState } from "react";
import { api, describeError, money, type Grant } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useMandate } from "@/lib/mandate";
import { useSession } from "@/lib/session";

type RevokeResult = {
  grant_id: string;
  status: string;
  already: boolean;
  reclaimed?: number;
  released_reservations?: number;
  in_flight_count?: number;
  in_flight_amount?: number;
  stranded_on_root?: number;
  target_grant_id?: string;
};

export default function RevokeControl({ g, currency }: { g: Grant; currency: string }) {
  const { session } = useSession();
  const { refresh } = useMandate();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<RevokeResult | null>(null);

  async function revoke() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    try {
      setResult(await api<RevokeResult>(session.key, `/grants/${g.id}/revoke`, { method: "POST", body: {} }));
      setConfirming(false);
      toast("Grant revoked");
      refresh();
    } catch (e) {
      setErr(describeError(e, "Revoke failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      {result && (
        <div role="status" style={{ border: "1px solid var(--rule)", background: "var(--paper)", padding: "0.75rem", marginBottom: "0.5rem" }}>
          <p style={{ margin: 0, fontWeight: 600 }}>{result.already ? "Already " : "Grant "}{result.status}</p>
          {!result.already && (
            <dl style={{ margin: "0.25rem 0 0", display: "grid", gridTemplateColumns: "1fr auto", columnGap: "0.75rem", rowGap: "0.25rem" }}>
              <dt className="dim">Reclaimed</dt><dd style={{ margin: 0, textAlign: "right" }}>{money(result.reclaimed ?? 0, currency)}</dd>
              <dt className="dim">Reservations released</dt><dd style={{ margin: 0, textAlign: "right" }}>{result.released_reservations ?? 0}</dd>
              <dt className="dim">In flight (cannot be recalled)</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>{result.in_flight_count ?? 0} · {money(result.in_flight_amount ?? 0, currency)}</dd>
              {!!result.stranded_on_root && (
                <><dt className="dim">Stranded on root</dt><dd style={{ margin: 0, textAlign: "right" }}>{money(result.stranded_on_root, currency)}</dd></>
              )}
            </dl>
          )}
        </div>
      )}
      {err && <p role="alert" className="alert">{err}</p>}
      {g.status !== "active" ? null : !confirming ? (
        <button onClick={() => setConfirming(true)} className="btn ghost small wide" style={{ color: "var(--refuse)", borderColor: "var(--refuse)" }}>
          Revoke this grant
        </button>
      ) : (
        <div style={{ border: "1px solid var(--refuse)", padding: "0.75rem" }}>
          <p style={{ margin: 0 }}>
            This cuts off the holder and every grant below it immediately. Unspent funds return to the parent. Transfers
            already in flight cannot be recalled.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button disabled={busy} onClick={() => void revoke()} className="btn small" style={{ background: "var(--refuse)" }}>
              {busy ? "Revoking…" : "Confirm revoke"}
            </button>
            <button disabled={busy} onClick={() => setConfirming(false)} className="btn ghost small">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
