"use client";
// The API key lives in React state only: never localStorage, never a cookie, gone on reload.
import { createContext, useContext, useState, type ReactNode } from "react";

type Session = { key: string; mandateId: string; kind?: string };
type Ctx = { session: Session | null; signIn: (s: Session) => void; signOut: () => void };

const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  return (
    <SessionCtx.Provider value={{ session, signIn: setSession, signOut: () => setSession(null) }}>
      {children}
    </SessionCtx.Provider>
  );
}

export function useSession(): Ctx {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("SessionProvider missing");
  return c;
}
