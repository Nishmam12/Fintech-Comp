"use client";
// The API key lives in React state only: never localStorage, never a cookie, gone on reload.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { describeError, ApiError, setAuthLostHandler } from "@/lib/api";

type Session = { key: string; mandateId: string; principalId: string; kind?: string };
type Ctx = {
  session: Session | null;
  // Shown on the sign-in screen after the session was dropped for a reason (expired key, disabled account).
  notice: string | null;
  signIn: (s: Session) => void;
  signOut: () => void;
  // After a key rotation the old key is dead; the new one replaces it in memory.
  replaceKey: (key: string) => void;
};

const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const signOut = useCallback(() => setSession(null), []);
  useEffect(() => {
    setAuthLostHandler((code) => {
      setNotice(describeError(new ApiError(401, code, ""), "Signed out"));
      setSession(null);
    });
    return () => setAuthLostHandler(null);
  }, []);

  return (
    <SessionCtx.Provider
      value={{
        session,
        notice,
        signIn: (s) => { setNotice(null); setSession(s); },
        signOut,
        replaceKey: (key) => setSession((s) => (s ? { ...s, key } : s)),
      }}
    >
      {children}
    </SessionCtx.Provider>
  );
}

export function useSession(): Ctx {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("SessionProvider missing");
  return c;
}
