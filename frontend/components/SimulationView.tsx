"use client";
// Screen 6: the attack panel. Runs a named attack against the unsafe baseline and the real kernel and shows the
// measured result exactly as the API returns it. Nothing here is computed in the browser.
import { useEffect, useState } from "react";
import { ApiError, describeError, listScenarios, money, runScenario, type SimResult, type SimSide } from "@/lib/api";
import Section, { Filler } from "@/components/ui/Section";
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

export const native = true;

// The API's summaries embed amounts as integer minor units ("reserved 90000 of 90000"). Display only: any bare integer of
// four digits or more is written as money. The measured result itself is never recomputed here.
const clamp2 = { whiteSpace: "normal", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.2, fontSize: "0.8125rem" } as const;
const asMoney = (s: string) => s.replace(/\b\d{4,}\b/g, (n) => money(Number(n)));

// violated === null means the scenario has no baseline to compare against (informational).
function Cell({ side, kernel }: { side: SimSide; kernel: boolean }) {
  const na = (side.violated as boolean | null) === null;
  const word = na ? "Not applicable" : side.violated ? "Broken" : "Held";
  const t = na ? "dim" : side.violated ? "no" : kernel ? "ok" : "dim";
  return (
    <div className={`slip verdict ${t}`} title={asMoney(side.summary)}>
      <span className="stamp">{word}</span><p style={clamp2}>{asMoney(side.summary)}</p>
    </div>
  );
}

export default function SimulationView() {
  const { session } = useSession();
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, SimResult>>({});
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const key = session?.key;
  const humanOnly = session?.kind !== undefined && session.kind !== "human";

  useEffect(() => {
    if (!key || humanOnly) return;
    let live = true;
    listScenarios(key)
      .then((r) => { if (live) { setScenarios(r.scenarios); setLoaded(true); } })
      .catch((e) => { if (live) setErr(describeError(e, "Could not load scenarios")); });
    return () => { live = false; };
  }, [key, humanOnly]);

  if (!key) return null;
  if (humanOnly) {
    return <Section span={12} title="Attack lab"><Filler>Attack simulations can only be run with a human key.</Filler></Section>;
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
    <Section
      span={12}
      title="Attack lab"
      meta={
        <button className="btn small" disabled={running !== null || scenarios.length === 0} onClick={() => void runAll()}>
          {progress ? `Running ${progress}…` : "Run all attacks"}
        </button>
      }
      head={
        <div className="row head atk">
          <span>Attack</span><span className="hide-s">What it tests</span><span>Without the kernel</span><span>With Budget Kernel</span><span />
        </div>
      }
      foot={<span>Each attack runs twice on real Postgres: against an intentionally unsafe baseline, and against the kernel. Results are measured, not scripted.</span>}
    >
      {err && <p role="alert" className="alert">{err}</p>}
      {!loaded && !err && <Filler>Loading attacks…</Filler>}
      <div className="attack-body" style={{ flex: 1, minHeight: 0 }}>
        {scenarios.map((name) => {
          const r = results[name];
          return (
            <div key={name} className="row atk">
              <div className="name"><b>{r?.title ?? label(name)}</b>{r?.informational && <em>Informational</em>}</div>
              <span className="hide-s"><span style={{ ...clamp2, fontSize: "0.875rem" }}>{DESCRIPTIONS[name] ?? ""}</span></span>
              {r ? <Cell side={r.naive} kernel={false} /> : <div className="slip proposal"><span>Not run yet</span></div>}
              {r ? <Cell side={r.kernel} kernel /> : <div className="slip proposal"><span>Not run yet</span></div>}
              <button className="btn ghost small" disabled={running !== null} onClick={() => void run(name)}>
                {running === name ? "Running…" : r ? "Run again" : "Run"}
              </button>
            </div>
          );
        })}
      </div>
    </Section>
  );
}
