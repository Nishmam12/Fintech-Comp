"use client";
// Sign-in: username and password (a login session), or create an account when the server allows it, or an API key
// (agents and operators). The one-tap demo accounts exist only in development builds (docs/plans/LOGIN_PLAN.md, R23).
import { useEffect, useState } from "react";
import {
  authConfig, describeError, getMe, listMandates, loginRequest, money, signupRequest,
  type AuthResult, type MandateSummary, type Me,
} from "@/lib/api";
import Cheque from "@/components/ui/Cheque";
import { PasswordInput } from "@/components/ui/PasswordInput";
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
      <div className="or">Or sign in with your own account</div>
    </>
  );
}

type Tab = "signin" | "signup";

export default function SignIn() {
  const { signIn, notice } = useSession();
  const [tab, setTab] = useState<Tab>("signin");
  const [signupOpen, setSignupOpen] = useState(false);
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [useKey, setUseKey] = useState(false);
  const [key, setKey] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [mandates, setMandates] = useState<MandateSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The credential being signed in with (a session token, or a key typed or from a demo button), kept out of any field.
  const [activeKey, setActiveKey] = useState("");

  useEffect(() => {
    let live = true;
    authConfig().then((c) => { if (live) setSignupOpen(c.signup); }).catch(() => undefined);
    return () => { live = false; };
  }, []);

  // With a credential in hand: who is it, and which mandates can it open? None means the setup screen follows.
  async function enter(k: string, who?: Me) {
    const person = who ?? (await getMe(k));
    const { mandates: list } = await listMandates(k);
    setMe(person);
    setActiveKey(k);
    if (list.length === 0) signIn({ key: k, mandateId: null, principalId: person.principal_id, kind: person.kind, name: person.name });
    else if (list.length === 1) signIn({ key: k, mandateId: list[0].id, principalId: person.principal_id, kind: person.kind, name: person.name });
    else setMandates(list);
  }

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(describeError(e, "Sign-in failed"));
    } finally {
      setBusy(false);
    }
  }

  const fromAuth = (r: AuthResult) => enter(r.session_token, { principal_id: r.principal.principal_id, name: r.principal.name, kind: r.principal.kind });

  const submitLogin = (e: React.FormEvent) => { e.preventDefault(); void run(async () => fromAuth(await loginRequest(username, password))); };
  const submitSignup = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== repeat) { setErr("The two passwords are not the same."); return; }
    void run(async () => fromAuth(await signupRequest(name, username, password)));
  };
  const submitKey = (e: React.FormEvent) => { e.preventDefault(); void run(() => enter(key.trim())); };

  function reset() {
    setMe(null); setMandates(null); setKey(""); setActiveKey(""); setPassword(""); setRepeat("");
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
        <div className="sec-head"><h2 className="fig">{mandates ? "Choose a mandate" : tab === "signup" ? "Create account" : "Sign in"}</h2></div>
        {notice && <p role="alert" className="alert">{notice}</p>}
        {mandates ? (
          <div style={{ marginTop: "1rem" }}>
            <p style={{ margin: "0 0 0.75rem" }}>Signed in as <b className="wrap-anywhere">{me?.name}</b>.</p>
            <div className="demo" style={{ flex: "none" }}>
              {mandates.map((m) => (
                <button key={m.id} className="btn ghost"
                  onClick={() => signIn({ key: activeKey, mandateId: m.id, principalId: me?.principal_id ?? "", kind: me?.kind, name: me?.name })}>
                  {money(m.total, m.currency)}
                  <span>{m.role}, {m.status}, expires {new Date(m.expires_at).toLocaleDateString()}</span>
                </button>
              ))}
            </div>
            <button onClick={reset} className="btn ghost wide" style={{ marginTop: "0.75rem" }}>Use a different account</button>
          </div>
        ) : (
          <>
            {demo && <DemoButtons raw={demo} busy={busy} onPick={(k) => void run(() => enter(k))} />}
            {!useKey && (
              <>
                {signupOpen && (
                  <div role="tablist" aria-label="Sign in or create an account" style={{ display: "flex", gap: "1.5rem", marginTop: "1rem" }}>
                    {(["signin", "signup"] as Tab[]).map((t) => (
                      <button key={t} role="tab" aria-selected={tab === t} className="linkbtn"
                        style={{ fontWeight: tab === t ? 700 : 400, textDecoration: tab === t ? "underline" : "none", fontSize: "1rem" }}
                        onClick={() => { setTab(t); setErr(null); }}>
                        {t === "signin" ? "Sign in" : "Create account"}
                      </button>
                    ))}
                  </div>
                )}
                <form onSubmit={tab === "signup" && signupOpen ? submitSignup : submitLogin}>
                  {tab === "signup" && signupOpen && (
                    <>
                      <label htmlFor="su-name">Your name</label>
                      <input id="su-name" className="field" autoComplete="name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
                    </>
                  )}
                  <label htmlFor="su-user">Username</label>
                  <input id="su-user" className="field" autoComplete="username" required maxLength={64} autoCapitalize="none" spellCheck={false}
                    value={username} onChange={(e) => setUsername(e.target.value)} />
                  <label htmlFor="su-pass">Password</label>
                  <PasswordInput id="su-pass" required maxLength={128}
                    autoComplete={tab === "signup" && signupOpen ? "new-password" : "current-password"}
                    value={password} onChange={(e) => setPassword(e.target.value)} />
                  {tab === "signup" && signupOpen && (
                    <>
                      <label htmlFor="su-repeat">Repeat the password</label>
                      <PasswordInput id="su-repeat" required maxLength={128} autoComplete="new-password"
                        value={repeat} onChange={(e) => setRepeat(e.target.value)} />
                      <p className="tag" style={{ margin: "0.5rem 0 0" }}>At least 8 characters. Your username can be an email address.</p>
                    </>
                  )}
                  {err && <p role="alert" className="alert">{err}</p>}
                  <button disabled={busy} className="btn wide" style={{ marginTop: "0.75rem" }}>
                    {busy ? "Checking…" : tab === "signup" && signupOpen ? "Create account" : "Sign in"}
                  </button>
                </form>
              </>
            )}
            {useKey && (
              <form onSubmit={submitKey}>
                <label htmlFor="si-key">API key</label>
                <PasswordInput id="si-key" autoComplete="off" required value={key} onChange={(e) => setKey(e.target.value)} />
                {err && <p role="alert" className="alert">{err}</p>}
                <button disabled={busy} className="btn wide" style={{ marginTop: "0.75rem" }}>{busy ? "Checking…" : "Sign in with the key"}</button>
              </form>
            )}
            <p style={{ marginTop: "1rem", fontSize: "0.8125rem" }}>
              <button type="button" className="linkbtn" onClick={() => { setUseKey(!useKey); setErr(null); }}>
                {useKey ? "Use a username and password instead" : "Use an API key instead (agents and operators)"}
              </button>
            </p>
          </>
        )}
        <p className="dim" style={{ fontSize: "0.8125rem", marginTop: "0.5rem" }}>The sign-in is kept in this tab&apos;s memory only and disappears on reload.</p>
      </section>
    </div>
  );
}
