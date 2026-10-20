"use client";
// Shared server state for the signed-in mandate. All screens read the same snapshot; `refresh` re-reads it.
//
// One read at a time: a refresh asked for while a read is in flight is remembered and runs right after it, so the snapshot
// always catches up. (Cancelling the in-flight read on every refresh starved the screen whenever the server took longer to
// answer than the poll interval, which is the normal case against a database a continent away.)
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { describeError, getState, type MandateState } from "@/lib/api";
import { useSession } from "@/lib/session";

type Ctx = { state: MandateState | null; error: string | null; refresh: () => void; updatedAt: Date | null };
const MandateCtx = createContext<Ctx | null>(null);

export function MandateProvider({ children }: { children: ReactNode }) {
  const { session } = useSession();
  const [state, setState] = useState<MandateState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const loadRef = useRef<() => void>(() => {});

  useEffect(() => {
    if (!session) return;
    let alive = true;
    let inFlight = false;
    let again = false;
    const load = async () => {
      if (inFlight) { again = true; return; }
      inFlight = true;
      try {
        const st = await getState(session.key, session.mandateId);
        if (alive) { setState(st); setError(null); setUpdatedAt(new Date()); }
      } catch (e) {
        if (alive) setError(describeError(e, "Could not load the mandate"));
      } finally {
        inFlight = false;
        if (again && alive) { again = false; void load(); }
      }
    };
    loadRef.current = () => { void load(); };
    void load();
    return () => { alive = false; loadRef.current = () => {}; };
  }, [session]);

  const refresh = useCallback(() => loadRef.current(), []);
  return <MandateCtx.Provider value={{ state, error, refresh, updatedAt }}>{children}</MandateCtx.Provider>;
}

export function useMandate(): Ctx {
  const c = useContext(MandateCtx);
  if (!c) throw new Error("MandateProvider missing");
  return c;
}
