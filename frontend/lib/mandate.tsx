"use client";
// Shared server state for the signed-in mandate. All screens read the same snapshot; `refresh` re-reads it.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, getState, type MandateState } from "@/lib/api";
import { useSession } from "@/lib/session";

type Ctx = { state: MandateState | null; error: string | null; refresh: () => void };
const MandateCtx = createContext<Ctx | null>(null);

export function MandateProvider({ children }: { children: ReactNode }) {
  const { session } = useSession();
  const [state, setState] = useState<MandateState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!session) return;
    let live = true;
    getState(session.key, session.mandateId)
      .then((st) => { if (live) { setState(st); setError(null); } })
      .catch((e) => { if (live) setError(e instanceof ApiError ? `${e.code}: ${e.message}` : "Could not load the mandate"); });
    return () => { live = false; };
  }, [session, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return <MandateCtx.Provider value={{ state, error, refresh }}>{children}</MandateCtx.Provider>;
}

export function useMandate(): Ctx {
  const c = useContext(MandateCtx);
  if (!c) throw new Error("MandateProvider missing");
  return c;
}
