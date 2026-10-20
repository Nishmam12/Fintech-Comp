"use client";
// The API key or login session token lives in React state only: never localStorage, never a cookie, gone on reload.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { describeError, ApiError, isSessionToken, logoutRequest, setAuthLostHandler } from "@/lib/api";

// mandateId is null for a person who has signed in but has not set up a mandate yet (the setup screen follows).
type Session = { key: string; mandateId: string | null; principalId: string; kind?: string; name?: string };
type Ctx = {
  session: Session | null;
  // Shown on the sign-in screen after the session was dropped for a reason (expired key, disabled account).
  notice: string | null;
  signIn: (s: Session) => void;
  signOut: () => void;
  setMandate: (id: string) => void;
  // After a key rotation the old key is dead; the new one replaces it in memory.
  replaceKey: (key: string) => void;
};

const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const live = useRef(false);   // a notice is only for a session that was dropped, not for a failed sign-in attempt
  const activeKey = useRef<string | null>(null);
  useEffect(() => { live.current = session !== null; activeKey.current = session?.key ?? null; }, [session]);

  // A login session is ended on the server too (best effort: the screen clears either way).
  const signOut = useCallback(() => {
    const k = activeKey.current;
    activeKey.current = null;
    live.current = false;
    if (k && isSessionToken(k)) void logoutRequest(k).catch(() => undefined);
    setSession(null);
  }, []);
  useEffect(() => {
    setAuthLostHandler((code, failedKey) => {
      if (!live.current || failedKey !== activeKey.current) return;
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
        setMandate: (id) => setSession((s) => (s ? { ...s, mandateId: id } : s)),
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
