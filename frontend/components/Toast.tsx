"use client";
// A small shared toast (BK-516). One message at a time, announced politely, gone after 4 s.
// Text is always one of our own fixed phrases ("Grant suspended"); never model or user text.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

const DISMISS_MS = 4000;
const ToastCtx = createContext<(text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [text, setText] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((t: string) => {
    if (timer.current) clearTimeout(timer.current);
    setText(t);
    timer.current = setTimeout(() => setText(null), DISMISS_MS);
  }, []);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-20 flex justify-center px-4 lg:bottom-6">
        <div role="status" className="contents">
          {text && (
            <p
              className="pointer-events-auto"
              style={{ margin: 0, background: "var(--ink)", color: "var(--paper)", padding: "0.75rem 1.5rem", fontSize: "0.9375rem", fontWeight: 600 }}
            >
              {text}
            </p>
          )}
        </div>
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
