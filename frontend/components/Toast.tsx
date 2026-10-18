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
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-20 flex justify-center px-4 lg:bottom-6 lg:pl-64">
        <div role="status" className="contents">
          {text && (
            <p className="pointer-events-auto rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white ring-1 ring-ink-soft">
              {text}
            </p>
          )}
        </div>
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
