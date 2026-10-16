"use client";
// BK-323 kill switch: revoke one grant (and everything below it) with a confirmation step.
// The result is shown exactly as the API returns it. In-flight transfers cannot be recalled, so they are
// reported separately and never described as reclaimed.
import { useState } from "react";
import { api, describeError, money, type Grant } from "@/lib/api";
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
      refresh();
    } catch (e) {
      setErr(describeError(e, "Revoke failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3">
      {result && (
        <div role="status" className="mb-2 rounded-md border border-line bg-background p-3 text-sm">
          <p className="font-semibold">{result.already ? "Already " : "Grant "}{result.status}</p>
          {!result.already && (
            <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1">
              <dt className="text-muted">Reclaimed</dt><dd className="text-right">{money(result.reclaimed ?? 0, currency)}</dd>
              <dt className="text-muted">Reservations released</dt><dd className="text-right">{result.released_reservations ?? 0}</dd>
              <dt className="text-muted">In flight (cannot be recalled)</dt>
              <dd className="text-right">{result.in_flight_count ?? 0} · {money(result.in_flight_amount ?? 0, currency)}</dd>
              {!!result.stranded_on_root && (
                <><dt className="text-muted">Stranded on root</dt><dd className="text-right">{money(result.stranded_on_root, currency)}</dd></>
              )}
            </dl>
          )}
        </div>
      )}
      {err && <p role="alert" className="mb-2 text-sm text-bad">{err}</p>}
      {g.status !== "active" ? null : !confirming ? (
        <button onClick={() => setConfirming(true)} className="btn-ghost w-full border-bad/50 text-bad">
          Revoke this grant
        </button>
      ) : (
        <div className="rounded-md border border-bad/50 bg-bad/10 p-3">
          <p className="text-sm">
            This cuts off the holder and every grant below it immediately. Unspent funds return to the parent. Transfers
            already in flight cannot be recalled.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button disabled={busy} onClick={() => void revoke()} className="min-h-12 rounded-md bg-bad px-3 text-base font-medium text-white disabled:opacity-60">
              {busy ? "Revoking…" : "Confirm revoke"}
            </button>
            <button disabled={busy} onClick={() => setConfirming(false)} className="btn-ghost min-h-12">Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
