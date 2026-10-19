"use client";
// BK-413 on the revision 3 system: identity on the left, the key and sign out on the right.
// Rotating shows the new key once; the old one stops working at once, so the session switches to the new key in
// memory. Nothing is stored anywhere else.
import { useState } from "react";
import { describeError, money, rotateKey } from "@/lib/api";
import Section, { Filler } from "@/components/ui/Section";
import { useToast } from "@/components/Toast";
import { useMandate } from "@/lib/mandate";
import { useRole } from "@/lib/role";
import { useSession } from "@/lib/session";

const KV = "12rem minmax(0,1fr)";
const ROLE_TEXT = { owner: "Owner of this mandate", manager: "Manager", agent: "Agent" } as const;

export const native = true;

export default function SettingsView() {
  const { session, replaceKey, signOut } = useSession();
  const { state } = useMandate();
  const { role } = useRole();
  const toast = useToast();
  // undefined: the server has not told us; null: the key does not expire.
  const [expiry, setExpiry] = useState<string | null | undefined>(undefined);
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
      setExpiry(r.key_expires_at);
      toast("Key rotated");
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

  const serial = state?.mandate.id.replace(/-/g, "").slice(0, 8).toUpperCase();
  const expiryText = expiry ? new Date(expiry).toLocaleString() : expiry === null ? "Does not expire" : "Not reported by the server until you rotate the key";

  return (
    <>
      <Section span={6} title="You" meta="Signed in with an API key">
        <div className="row" style={{ gridTemplateColumns: KV }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Name</span><b style={{ overflowWrap: "anywhere" }}>{session?.name ?? "Unknown"}</b></div>
        <div className="row" style={{ gridTemplateColumns: KV }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Role</span><span>{ROLE_TEXT[role]}</span></div>
        {state && serial && (
          <div className="row" style={{ gridTemplateColumns: KV }}>
            <span className="tag" style={{ fontSize: "0.9375rem" }}>Mandate</span>
            <span><span className="serial">No. {serial.slice(0, 4)} {serial.slice(4)}</span>, {money(state.mandate.total, state.mandate.currency)}</span>
          </div>
        )}
        <div className="row" style={{ gridTemplateColumns: KV }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Key expires</span><span>{expiryText}</span></div>
        <div className="row" style={{ gridTemplateColumns: KV }}><span className="tag" style={{ fontSize: "0.9375rem" }}>Settlement</span><span>Base Sepolia testnet, test USDC</span></div>
        <Filler />
        <p className="explain">The key is kept in this tab&rsquo;s memory only and disappears when you reload.</p>
      </Section>

      <Section span={6} title="Your key" meta="Rotate if it may have leaked">
        <div className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
          <div className="name"><b>Rotate key</b><em>Issues a new key and disables this one at once</em></div>
          <button className="btn ghost small" disabled={confirming || !!fresh} onClick={() => setConfirming(true)}>Rotate key</button>
        </div>
        {err && <p role="alert" className="alert">{err}</p>}
        {confirming && (
          <div className="manage" style={{ paddingLeft: 0 }}>
            <p style={{ margin: "0 0 0.75rem" }}>The current key stops working as soon as you confirm. This session continues on the new key.</p>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="btn small" style={{ background: "var(--refuse)" }} disabled={busy} onClick={() => void rotate()}>{busy ? "Rotating…" : "Confirm rotate"}</button>
              <button className="btn ghost small" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </div>
        )}
        {fresh && (
          <div className="manage" style={{ paddingLeft: 0 }}>
            <p className="ok" style={{ margin: 0, fontWeight: 600 }}>New key. Shown once; store it now.</p>
            <p style={{ margin: "0.5rem 0 0.75rem", padding: "0.5rem 0.75rem", border: "1px solid var(--rule)", background: "var(--paper)", fontFamily: "monospace", fontSize: "0.8125rem", wordBreak: "break-all", userSelect: "all" }}>{fresh}</p>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="btn small" onClick={() => void copy()}>{copied ? "Copied" : "Copy key"}</button>
              <button className="btn ghost small" onClick={() => { setFresh(null); setCopied(false); }}>Done, hide it</button>
            </div>
          </div>
        )}
        <div className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
          <div className="name"><b>Sign out</b><em>Forget the key in this tab</em></div>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
        <Filler />
        <p className="explain">After rotating, the new key is shown once. The old key stops working at once.</p>
      </Section>
    </>
  );
}
