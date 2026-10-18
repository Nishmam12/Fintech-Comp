"use client";
import { useState } from "react";
import { describeError, getMe, listMandates, money, type Me, type MandateSummary } from "@/lib/api";
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
    <div className="flex flex-col gap-2">
      {Object.entries(keys).map(([label, k]) => (
        <button key={label} type="button" disabled={busy} onClick={() => onPick(k)} className="btn-primary">
          Continue as {label}
        </button>
      ))}
      <p className="mt-2 text-sm text-muted">Or paste an API key</p>
    </div>
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

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
    <aside className="flex flex-col justify-between bg-ink px-6 py-8 text-ink-text lg:px-14 lg:py-16">
      <p className="fig text-2xl text-white">Budget Kernel</p>
      <div className="py-10 lg:py-0">
        <p className="fig max-w-md text-4xl text-white lg:text-6xl">Models propose. The kernel decides.</p>
        <p className="mt-4 max-w-md text-base lg:text-lg">
          Give an AI agent a budget it cannot overspend. Every payment is checked against the owner&apos;s limits before any money moves.
        </p>
      </div>
      <p className="hidden text-sm lg:block">Testnet settlement on Base Sepolia.</p>
    </aside>
    <main className="flex w-full max-w-md flex-col justify-center gap-6 px-6 py-10 lg:mx-auto">
      <h1 className="fig text-3xl">Sign in</h1>
      {notice && (
        <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{notice}</p>
      )}
      {mandates ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            Signed in as <span className="font-semibold wrap-anywhere">{me?.name}</span> ({me?.kind}). Choose a mandate:
          </p>
          {mandates.length === 0 && <p className="rounded-lg border border-line bg-card p-3 text-sm text-muted">This key has no mandates.</p>}
          <ul className="flex flex-col gap-2">
            {mandates.map((m) => (
              <li key={m.id}>
                <button
                  onClick={() => signIn({ key: activeKey, mandateId: m.id, principalId: me?.principal_id ?? "", kind: me?.kind, name: me?.name })}
                  className="min-h-14 w-full rounded-lg border border-line bg-card p-3 text-left"
                >
                  <span className="block font-semibold">{money(m.total, m.currency)}</span>
                  <span className="block text-xs text-muted">
                    {m.role} · {m.status} · <span className="font-mono">{m.id.slice(0, 8)}</span> · expires {new Date(m.expires_at).toLocaleDateString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button onClick={reset} className="btn-ghost">Use a different key</button>
        </div>
      ) : (
        <>
        {process.env.NEXT_PUBLIC_DEMO_KEYS ? (
          <DemoButtons raw={process.env.NEXT_PUBLIC_DEMO_KEYS} busy={busy} onPick={(k) => void attempt(k)} />
        ) : null}
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            {process.env.NEXT_PUBLIC_DEMO_KEYS ? "API key" : "Paste your API key"}
            <input
              type="password"
              autoComplete="off"
              required
              value={key}
              onChange={(e) => setKey(e.target.value)}
              className="field"
            />
          </label>
          {err && (
            <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
              {err}
            </p>
          )}
          <button disabled={busy} className="btn-primary">
            {busy ? "Checking…" : "Sign in"}
          </button>
        </form>
        </>
      )}
      <p className="text-xs text-muted">The key is kept in this tab&apos;s memory only and disappears on reload.</p>
    </main>
    </div>
  );
}
