"use client";
// BK-413: rotate the API key. The new key is shown once; the old one stops working at once, so the session
// switches to the new key in memory. Nothing is stored anywhere else.
import { useState } from "react";
import { describeError, rotateKey } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SettingsView() {
  const { session, replaceKey } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [fresh, setFresh] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function rotate() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await rotateKey(session.key);
      replaceKey(r.api_key);
      setFresh(r.api_key);
      setConfirming(false);
    } catch (e) {
      setErr(describeError(e, "Could not rotate the key"));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!fresh) return;
    try {
      await navigator.clipboard.writeText(fresh);
      setCopied(true);
    } catch {
      setErr("Copy failed. Select the key and copy it by hand.");
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="rounded-lg border border-line bg-card p-3">
        <h3 className="text-sm font-semibold">API key</h3>
        <p className="mt-1 text-sm text-muted">
          Rotating issues a new key and disables the current one immediately. Any other device or script using the old key
          will be signed out.
        </p>
        {err && <p role="alert" className="mt-2 text-sm text-bad">{err}</p>}
        {fresh ? (
          <div className="mt-3 rounded-md border border-ok/40 bg-ok/10 p-3">
            <p className="text-sm font-semibold text-ok">New key. Shown once; store it now.</p>
            <p className="mt-2 break-all rounded border border-line bg-background p-2 font-mono text-xs select-all">{fresh}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button onClick={() => void copy()} className="btn-primary">{copied ? "Copied" : "Copy key"}</button>
              <button onClick={() => { setFresh(null); setCopied(false); }} className="btn-ghost min-h-12">Done, hide it</button>
            </div>
          </div>
        ) : !confirming ? (
          <button onClick={() => setConfirming(true)} className="btn-ghost mt-3 w-full">Rotate key</button>
        ) : (
          <div className="mt-3 rounded-md border border-bad/50 bg-bad/10 p-3">
            <p className="text-sm">The current key stops working as soon as you confirm. This session continues on the new key.</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button disabled={busy} onClick={() => void rotate()} className="min-h-12 rounded-md bg-bad px-3 text-base font-medium text-white disabled:opacity-60">
                {busy ? "Rotating…" : "Confirm rotate"}
              </button>
              <button disabled={busy} onClick={() => setConfirming(false)} className="btn-ghost min-h-12">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
