"use client";
import { useState } from "react";
import { describeError, getMe, listMandates, money, type Me, type MandateSummary } from "@/lib/api";
import Cheque from "@/components/ui/Cheque";
import { useSession } from "@/lib/session";

// Dev-only one-click sign-in (BK-511). scripts/demo_seed.py writes NEXT_PUBLIC_DEMO_KEYS to the gitignored .env.local.
// Next inlines the value at build time, so a build without it contains no keys and no demo buttons
// (the only reference is the literal `process.env.NEXT_PUBLIC_DEMO_KEYS` below, which the bundler folds away).
// The keys stay in this closure: they are never rendered, logged or put in a field.
function parseDemoKeys(raw: string): Record<string, string> {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, v]) => typeof v === "string" && v));
  } catch {
    return {};
  }
}

function DemoButtons({ raw, busy, onPick }: { raw: string; busy: boolean; onPick: (key: string) => void }) {
  const keys = parseDemoKeys(raw);
  if (Object.keys(keys).length === 0) return null;
  return (
    <>
      <div className="demo">
        {Object.entries(keys).map(([label, k]) => {
          const m = label.match(/^(.*?)\s*\((.*)\)$/); // "Nabil (owner)" -> name and role
          const name = m ? m[1] : label, role = m ? m[2][0].toUpperCase() + m[2].slice(1) : "";
          return (
            <button key={label} type="button" disabled={busy} onClick={() => onPick(k)} className="btn ghost" aria-label={`Continue as ${label}`}>
              {name}<span>{role}</span>
            </button>
          );
        })}
      </div>
      <div className="or">Or paste an API key</div>
    </>
  );
}

export default function SignIn() {
  const { signIn, notice } = useSession();
  const [key, setKey] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [mandates, setMandates] = useState<MandateSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The key being signed in with (typed or a demo button), kept out of the input so demo keys never reach the DOM.
  const [activeKey, setActiveKey] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await attempt(key.trim());
  }

  async function attempt(k: string) {
    setBusy(true);
    setErr(null);
    try {
      // The key alone identifies the caller: /me verifies it, /mandates lists what it may open.
      const who = await getMe(k);
      const { mandates: list } = await listMandates(k);
      setMe(who);
      setActiveKey(k);
      if (list.length === 1) signIn({ key: k, mandateId: list[0].id, principalId: who.principal_id, kind: who.kind, name: who.name });
      else setMandates(list);
    } catch (e) {
      setErr(describeError(e, "Sign-in failed"));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setMe(null);
    setMandates(null);
    setKey("");
    setActiveKey("");
  }

  const demo = process.env.NEXT_PUBLIC_DEMO_KEYS;
  return (
    <div className="signin">
      <Cheque inner="">
        <b className="fig" style={{ fontSize: "1.25rem" }}>Budget Kernel</b>
        <div>
          <h1 className="tagline fig">Models propose. The kernel decides.</h1>
          <p className="note" style={{ maxWidth: "34rem" }}>
            Give an AI agent a budget it cannot overspend. Every payment is checked against the owner&apos;s limits before any money moves.
          </p>
        </div>
        <span className="serial dim">Settles on Base Sepolia testnet</span>
      </Cheque>
      <section className="side">
        <div className="sec-head"><h2 className="fig">Sign in</h2><span className="meta">{demo && !mandates ? "Demo accounts" : ""}</span></div>
        {notice && <p role="alert" className="alert">{notice}</p>}
        {mandates ? (
          <div style={{ marginTop: "1rem" }}>
            <p style={{ margin: "0 0 0.75rem" }}>Signed in as <b className="wrap-anywhere">{me?.name}</b> ({me?.kind}). Choose a mandate:</p>
            {mandates.length === 0 && <p className="tag">This key has no mandates.</p>}
            <div className="demo" style={{ flex: "none" }}>
              {mandates.map((m) => (
                <button key={m.id} className="btn ghost"
                  onClick={() => signIn({ key: activeKey, mandateId: m.id, principalId: me?.principal_id ?? "", kind: me?.kind, name: me?.name })}>
                  {money(m.total, m.currency)}
                  <span>{m.role}, {m.status}, expires {new Date(m.expires_at).toLocaleDateString()}</span>
                </button>
              ))}
            </div>
            <button onClick={reset} className="btn ghost wide" style={{ marginTop: "0.75rem" }}>Use a different key</button>
          </div>
        ) : (
          <>
            {demo ? <DemoButtons raw={demo} busy={busy} onPick={(k) => void attempt(k)} /> : <div style={{ height: "1rem" }} />}
            <form onSubmit={submit}>
              <input type="password" autoComplete="off" required value={key} onChange={(e) => setKey(e.target.value)} className="field"
                aria-label={demo ? "API key" : "Paste your API key"} placeholder={demo ? "" : "Paste your API key"} />
              {err && <p role="alert" className="alert">{err}</p>}
              <button disabled={busy} className="btn wide" style={{ marginTop: "0.75rem" }}>{busy ? "Checking…" : "Sign in"}</button>
            </form>
          </>
        )}
        <p className="dim" style={{ fontSize: "0.8125rem", marginTop: "1rem" }}>The key is kept in this tab&apos;s memory only and disappears on reload.</p>
      </section>
    </div>
  );
}
