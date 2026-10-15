"use client";
import { useState } from "react";
import { ApiError, getMe, listMandates, money, type Me, type MandateSummary } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SignIn() {
  const { signIn } = useSession();
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
      if (list.length === 1) signIn({ key: k, mandateId: list[0].id });
      else setMandates(list);
    } catch (e) {
      setErr(e instanceof ApiError ? `${e.code}: ${e.message}` : "Sign-in failed");
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
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-semibold">Budget Kernel</h1>
        <p className="mt-1 text-sm text-muted">Models propose. The kernel decides.</p>
      </div>
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
                  onClick={() => signIn({ key: key.trim(), mandateId: m.id })}
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
            API key
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
  );
}
