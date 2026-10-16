"use client";
// Screen 5: inference budget meter (GET /budget) and the live audit feed (GET /mandates/{id}/audit).
// Audit details can contain model- or user-derived text, so they are shown as plain text only.
import { useEffect, useRef, useState } from "react";
import { api, describeError, microUsd, type AuditEvent, type BudgetSnapshot } from "@/lib/api";
import { useSession } from "@/lib/session";

const POLL_MS = 3000;
const MAX_SHOWN = 300;

function BudgetMeter({ b }: { b: BudgetSnapshot }) {
  return (
    <div className="rounded-lg border border-line bg-card p-3">
      <h3 className="text-sm font-semibold">Inference budget · {b.month}</h3>
      {b.buckets.length === 0 && <p className="mt-2 text-sm text-muted">No budget buckets exist for this month yet.</p>}
      <ul className="mt-2 flex flex-col gap-3">
        {b.buckets.map((k) => (
          <li key={k.bucket}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium">{k.bucket}</span>
              <span className="text-muted">remaining {microUsd(k.remaining_micro)}</span>
            </div>
            <progress
              className="mt-1 h-2 w-full overflow-hidden rounded [&::-webkit-progress-bar]:bg-line [&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent"
              max={k.cap_micro_usd}
              value={k.spent_micro + k.reserved_micro}
              aria-label={`${k.bucket} budget used`}
            />
            <p className="mt-1 text-xs text-muted">
              spent {microUsd(k.spent_micro)} · reserved {microUsd(k.reserved_micro)} · cap {microUsd(k.cap_micro_usd)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ActivityView() {
  const { session } = useSession();
  const [budget, setBudget] = useState<BudgetSnapshot | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const lastId = useRef(0);

  useEffect(() => {
    if (!session) return;
    let live = true;
    async function poll() {
      if (!session || document.visibilityState !== "visible") return;
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
        if (fresh.length) setEvents((old) => [...[...fresh].reverse(), ...old].slice(0, MAX_SHOWN));
        setErr(null);
      } catch (e) {
        if (live) setErr(describeError(e, "Could not load activity"));
      }
    }
    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, [session]);

  return (
    <section className="flex flex-col gap-4">
      {err && <p role="alert" className="rounded-md border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{err}</p>}
      {budget ? <BudgetMeter b={budget} /> : !err && <p className="text-sm text-muted">Loading…</p>}
      <div className="rounded-lg border border-line bg-card p-3">
        <h3 className="text-sm font-semibold">Audit feed <span className="font-normal text-muted">(newest first, every 3 s)</span></h3>
        {events.length === 0 && <p className="mt-2 text-sm text-muted">No events yet.</p>}
        <ol className="mt-2 flex flex-col gap-2">
          {events.map((ev) => (
            <li key={ev.id} className="rounded border border-line px-2 py-1.5 text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{ev.kind}</span>
                <span className="text-xs text-muted">#{ev.id} · {new Date(ev.created_at).toLocaleTimeString()}</span>
              </div>
              {ev.detail && Object.keys(ev.detail).length > 0 && (
                <p className="mt-0.5 wrap-anywhere font-mono text-xs text-muted">{JSON.stringify(ev.detail)}</p>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
