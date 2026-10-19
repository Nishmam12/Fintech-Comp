"use client";
// Screen 6: the attack panel. Runs a named attack against the unsafe baseline and the real kernel and shows the
// measured result exactly as the API returns it. Nothing here is computed in the browser.
import { useEffect, useState } from "react";
import { ApiError, describeError, listScenarios, runScenario, type SimResult, type SimSide } from "@/lib/api";
import { useSession } from "@/lib/session";

const label = (s: string) => s.replace(/_/g, " ");

const DESCRIPTIONS: Record<string, string> = {
  concurrency_overspend: "Many payment requests arrive at the same instant. Can they spend more than the money that exists?",
  delegation_amplification: "An agent hands out more authority than it holds. Does total authority grow?",
  revoked_ancestor: "A manager's grant is revoked. Can the agents beneath it still spend?",
  revocation_race: "A revoke and a spend collide in either order. Does any live authority survive the revoke?",
  replay_duplicate: "The same payment request is delivered again and again. Is it paid once or many times?",
  split_purchases: "One big payment is split into small ones to dodge the per-payment limit. Does the hourly limit stop it?",
  limit_probing: "An agent keeps testing its limits with refused requests. Does it get suspended?",
};

// violated === null means the scenario has no baseline to compare against (informational).
function Side({ title, side, kernel }: { title: string; side: SimSide; kernel: boolean }) {
  const na = (side.violated as boolean | null) === null;
  const bad = !na && side.violated;
  const tone = na ? "border-line" : bad ? "border-bad/50 bg-bad/10" : kernel ? "border-ok/50 bg-ok/10" : "border-line";
  const metrics = Object.entries(side.metrics ?? {}).filter(([, v]) => typeof v === "number" || typeof v === "string");
  return (
    <div className={`rounded-md border p-3 ${tone}`}>
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-1 text-sm font-medium wrap-anywhere">{side.summary}</p>
      <p className={`fig mt-2 text-lg ${na ? "text-muted" : bad ? "text-bad" : "text-ok"}`}>{na ? "Not applicable" : bad ? "Violated" : "Held"}</p>
      {metrics.length > 0 && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 text-xs text-muted">
          {metrics.map(([k, v]) => (
            <div key={k} className="contents"><dt>{label(k)}</dt><dd className="fig wrap-anywhere text-right">{String(v)}</dd></div>
          ))}
        </dl>
      )}
    </div>
  );
}

// Flip to true once this view returns its own revision 3 <Section>s (see docs/handover/UI_R3.md); App then stops wrapping it.
export const native = false;

export default function SimulationView() {
  const { session } = useSession();
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
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
    return <p className="panel p-4 text-sm text-muted">Attack simulations can only be run with a human key.</p>;
  }

  async function run(name: string): Promise<boolean> {
    setRunning(name);
    setErr(null);
    try {
      const r = await runScenario(key!, name);
      setResults((prev) => ({ ...prev, [name]: r }));
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === "SIMULATION_RUNNING") setErr("Another simulation is already running. Try again in a moment.");
      else setErr(describeError(e, "Simulation failed"));
      return false;
    } finally {
      setRunning(null);
    }
  }

  // One after another, never in parallel: the API refuses a second run with SIMULATION_RUNNING.
  async function runAll() {
    for (let i = 0; i < scenarios.length; i++) {
      setProgress(`${i + 1} of ${scenarios.length}`);
      if (!(await run(scenarios[i]))) break;
    }
    setProgress(null);
  }

  return (
    <section className="flex flex-col gap-3">
      <p className="text-xs text-muted">
        Each attack runs twice on real Postgres: against an intentionally unsafe baseline and against the kernel. Outcomes are measured, not canned. Simulations use their own fresh mandate.
      </p>
      {err && <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{err}</p>}
      <div className="flex items-center gap-3">
        <button disabled={running !== null || scenarios.length === 0} onClick={() => void runAll()} className="btn-primary">
          {progress ? `Running ${progress}…` : "Run all attacks"}
        </button>
      </div>
      <ul className="flex flex-col gap-3">
        {scenarios.map((name) => {
          const r = results[name];
          return (
            <li key={name} className="panel p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold capitalize">{r?.title ?? label(name)}</p>
                  {DESCRIPTIONS[name] && <p className="mt-0.5 text-sm text-muted">{DESCRIPTIONS[name]}</p>}
                </div>
                <button disabled={running !== null} onClick={() => void run(name)} className="btn-primary shrink-0">
                  {running === name ? "Running…" : r ? "Run again" : "Run attack"}
                </button>
              </div>
              {r && (
                <div className="mt-3 flex flex-col gap-2">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Side title="Without the kernel" side={r.naive} kernel={false} />
                    <Side title="With Budget Kernel" side={r.kernel} kernel />
                  </div>
                  <p className="text-sm text-muted wrap-anywhere">{r.what_it_proves}</p>
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
