"use client";
// Screen 6: the attack panel. Runs a named attack against the unsafe baseline and the real kernel and shows the
// measured result exactly as the API returns it. Nothing here is computed in the browser.
import { useEffect, useState } from "react";
import { ApiError, describeError, listScenarios, runScenario, type SimResult, type SimSide } from "@/lib/api";
import { useSession } from "@/lib/session";

const label = (s: string) => s.replace(/_/g, " ");

function Side({ title, side, safeWhenHeld }: { title: string; side: SimSide; safeWhenHeld: boolean }) {
  const bad = side.violated;
  return (
    <div className={`rounded-lg border p-3 ${bad ? "border-bad/40 bg-bad/10" : safeWhenHeld ? "border-ok/40 bg-ok/10" : "border-line bg-card"}`}>
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className={`text-lg font-semibold ${bad ? "text-bad" : "text-ok"}`}>{bad ? "Violated" : "Held"}</p>
      <p className="mt-1 text-sm wrap-anywhere">{side.summary}</p>
    </div>
  );
}

export default function SimulationView() {
  const { session } = useSession();
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, SimResult>>({});
  const [err, setErr] = useState<string | null>(null);
  const key = session?.key;
  const humanOnly = session?.kind !== undefined && session.kind !== "human";

  useEffect(() => {
    if (!key || humanOnly) return;
    let live = true;
    listScenarios(key)
      .then((r) => { if (live) setScenarios(r.scenarios); })
      .catch((e) => { if (live) setErr(describeError(e, "Could not load scenarios")); });
    return () => { live = false; };
  }, [key, humanOnly]);

  if (!key) return null;
  if (humanOnly) {
    return <p className="rounded-lg border border-line bg-card p-4 text-sm text-muted">Attack simulations can only be run with a human key.</p>;
  }

  async function run(name: string) {
    setRunning(name);
    setErr(null);
    try {
      const r = await runScenario(key!, name);
      setResults((prev) => ({ ...prev, [name]: r }));
    } catch (e) {
      if (e instanceof ApiError && e.code === "SIMULATION_RUNNING") setErr("Another simulation is already running. Try again in a moment.");
      else setErr(describeError(e, "Simulation failed"));
    } finally {
      setRunning(null);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <p className="text-xs text-muted">
        Each attack runs twice on real Postgres: against an intentionally unsafe baseline and against the kernel. Outcomes are measured, not canned. Simulations use their own fresh mandate.
      </p>
      {err && <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{err}</p>}
      <ul className="flex flex-col gap-3">
        {scenarios.map((name) => {
          const r = results[name];
          return (
            <li key={name} className="rounded-lg border border-line bg-card p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold capitalize">{r?.title ?? label(name)}</p>
                <button disabled={running !== null} onClick={() => void run(name)} className="btn-primary">
                  {running === name ? "Running…" : r ? "Run again" : "Run attack"}
                </button>
              </div>
              {r && (
                <div className="mt-3 flex flex-col gap-2">
                  <p className="text-sm text-muted wrap-anywhere">{r.what_it_proves}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Side title="Unsafe baseline" side={r.naive} safeWhenHeld={false} />
                    <Side title="Budget Kernel" side={r.kernel} safeWhenHeld />
                  </div>
                  <p className="text-xs text-muted">Took {r.duration_ms} ms{r.informational ? " · informational scenario" : ""}</p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
