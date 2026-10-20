"use client";
// Screen 5 on the revision 3 system: a timeline of plain-language events grouped by day (8 columns) beside today's
// counters and the model budgets (4). Audit details can hold model- or user-derived text, so they are plain text only.
import { useEffect, useRef, useState } from "react";
import { api, describeError, microUsd, type AuditEvent, type Bucket, type BudgetSnapshot } from "@/lib/api";
import { describeEvent } from "@/lib/describe";
import Section, { Filler } from "@/components/ui/Section";
import { useSession } from "@/lib/session";

export const native = true;

const POLL_MS = 3000;
const MAX_SHOWN = 300;

const SYSTEM_NAMES: Record<string, string> = {
  global: "All models", primary: "Primary model", escalation: "Escalation model", retries: "Retries", eval: "Evaluation",
};

type Tone = "ok" | "wait" | "no" | "dim";
const TONE: Record<string, Tone> = {
  TX_RESERVED: "ok", TX_APPROVED: "ok", TX_SETTLED: "ok", GRANT_REINSTATED: "ok",
  TX_PROPOSED: "wait", GRANT_SUSPENDED: "wait",
  TX_REJECTED: "no", TX_REVIEW_REJECTED: "no", TX_SETTLE_FAILED: "no", GRANT_REVOKED: "no",
};
const tone = (k: string): Tone => TONE[k] ?? "dim";

const dayKey = (d: Date) => d.toDateString();
function dayLabel(d: Date, now: Date): string {
  if (dayKey(d) === dayKey(now)) return "Today";
  if (dayKey(d) === dayKey(new Date(now.getTime() - 86_400_000))) return "Yesterday";
  return d.toLocaleDateString([], { dateStyle: "medium" });
}
const hhmm = (d: Date) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function BudgetRow({ k }: { k: Bucket }) {
  const label = k.label && k.label !== k.bucket ? k.label : (SYSTEM_NAMES[k.bucket] ?? k.bucket);
  return (
    <div className="row" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
      <div className="name"><b>{label}</b><em>{microUsd(k.spent_micro + k.reserved_micro)} of {microUsd(k.cap_micro_usd)} used</em></div>
      <span className="num fig">{microUsd(k.remaining_micro)}</span>
    </div>
  );
}

export default function ActivityView() {
  const { session } = useSession();
  const [budget, setBudget] = useState<BudgetSnapshot | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const lastId = useRef(0);

  useEffect(() => {
    if (!session) return;
    let live = true;
    let busy = false; // one poll at a time: overlapping polls would both read after the same event id and add its events twice
    async function poll() {
      if (!session || busy || document.visibilityState !== "visible") return;
      busy = true;
      try {
        const b = await api<BudgetSnapshot>(session.key, "/budget");
        const fresh: AuditEvent[] = [];
        for (;;) {
          const r = await api<{ events: AuditEvent[] }>(
            session.key,
            `/mandates/${encodeURIComponent(session.mandateId)}/audit?after_id=${lastId.current}&limit=200`,
          );
          if (!live) return;
          fresh.push(...r.events);
          if (r.events.length === 0) break;
          lastId.current = r.events[r.events.length - 1].id;
          if (r.events.length < 200) break;
        }
        if (!live) return;
        setBudget(b);
        setLoaded(true);
        if (fresh.length) setEvents((old) => [...[...fresh].reverse(), ...old].slice(0, MAX_SHOWN));
        setErr(null);
      } catch (e) {
        if (live) setErr(describeError(e, "Could not load activity"));
      } finally {
        busy = false;
      }
    }
    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, [session]);

  const now = new Date();
  const today = events.filter((e) => dayKey(new Date(e.created_at)) === dayKey(now));
  // Counted from the events shown (the newest 300), which is plenty for one day of a demo mandate.
  const count = (...kinds: string[]) => today.filter((e) => kinds.includes(e.kind)).length;
  const counters: [string, number, string][] = [
    ["Approved", count("TX_RESERVED", "TX_APPROVED"), "ok"],
    ["Held", count("TX_PROPOSED"), "wait"],
    ["Refused", count("TX_REJECTED", "TX_REVIEW_REJECTED"), "no"],
    ["Suspended", count("GRANT_SUSPENDED"), ""],
  ];
  const agents = budget?.buckets.filter((k) => k.bucket.startsWith("principal:")) ?? [];
  const system = budget?.buckets.filter((k) => !k.bucket.startsWith("principal:")) ?? [];

  if (!loaded) {
    return (
      <Section span={12} title="What happened">
        {err && <p role="alert" className="alert">{err}</p>}
        <Filler>{err ? "Activity could not be loaded." : "Loading activity…"}</Filler>
      </Section>
    );
  }

  let lastDay = "";
  return (
    <>
      <Section span={8} title="What happened" meta="Newest first, updates every 3 s" live>
        {err && <p role="alert" className="alert">{err}</p>}
        {events.map((ev) => {
          const d = new Date(ev.created_at);
          const heading = dayKey(d) !== lastDay ? dayLabel(d, now) : null;
          lastDay = dayKey(d);
          return (
            <div key={ev.id} style={{ display: "contents" }}>
              {heading && <div className="day">{heading}</div>}
              <div className="row tl" title={ev.detail ? `#${ev.id} ${ev.kind} ${JSON.stringify(ev.detail)}` : `#${ev.id} ${ev.kind}`}>
                <i className={`dot ${tone(ev.kind)}`} aria-hidden="true" />
                <span>{describeEvent(ev)}</span>
                <span className="tag">{hhmm(d)}</span>
              </div>
            </div>
          );
        })}
        <Filler>{events.length === 0 ? "No events yet. Requests, approvals and grants appear here as they happen." : "Every event is hash-chained to the one before it."}</Filler>
      </Section>

      <Section
        span={4}
        title="Today"
        meta="This mandate"
        head={
          <div className="cells four">
            {counters.map(([label, n, t]) => (
              <div className="cell" key={label}><b className={`fig ${t}`}>{n}</b><span>{label}</span></div>
            ))}
          </div>
        }
      >
        <div className="day">Model budget this month</div>
        {agents.map((k) => <BudgetRow key={k.bucket} k={k} />)}
        {agents.length === 0 && <div className="row tag">No agent has a model budget yet.</div>}
        <div className="day">System budgets</div>
        {system.map((k) => <BudgetRow key={k.bucket} k={k} />)}
        <Filler />
        <p className="explain">
          A model call is reserved against these caps before it is made. At the cap the request is not sent and nothing is approved. Amounts in USD.
        </p>
      </Section>
    </>
  );
}
