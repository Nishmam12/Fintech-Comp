"use client";
import { useState } from "react";
import { ApiError, getState } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SignIn() {
  const { signIn } = useSession();
  const [key, setKey] = useState("");
  const [mandateId, setMandateId] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      // There is no "who am I" endpoint, so the key is verified by reading the mandate it should be able to see.
      await getState(key.trim(), mandateId.trim());
      signIn({ key: key.trim(), mandateId: mandateId.trim() });
    } catch (e) {
      setErr(e instanceof ApiError ? `${e.code}: ${e.message}` : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-semibold">Budget Kernel</h1>
        <p className="mt-1 text-sm text-muted">Models propose. The kernel decides.</p>
      </div>
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
        <label className="flex flex-col gap-1 text-sm">
          Mandate ID
          <input
            required
            autoComplete="off"
            value={mandateId}
            onChange={(e) => setMandateId(e.target.value)}
            className="field font-mono"
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
      <p className="text-xs text-muted">The key is kept in this tab&apos;s memory only and disappears on reload.</p>
    </main>
  );
}
