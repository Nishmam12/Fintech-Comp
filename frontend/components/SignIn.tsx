"use client";
import { useState } from "react";
import { describeError, getMe, listMandates, money, type Me, type MandateSummary } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SignIn() {
  const { signIn, notice } = useSession();
  const [key, setKey] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [mandates, setMandates] = useState<MandateSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const k = key.trim();
    try {
      // The key alone identifies the caller: /me verifies it, /mandates lists what it may open.
      const who = await getMe(k);
      const { mandates: list } = await listMandates(k);
      setMe(who);
      if (list.length === 1) signIn({ key: k, mandateId: list[0].id, principalId: who.principal_id, kind: who.kind });
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
                  onClick={() => signIn({ key: key.trim(), mandateId: m.id, principalId: me?.principal_id ?? "", kind: me?.kind })}
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
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Paste your API key
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
      )}
      <p className="text-xs text-muted">The key is kept in this tab&apos;s memory only and disappears on reload.</p>
    </main>
    </div>
  );
}
