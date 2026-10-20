"use client";
import { useState, type InputHTMLAttributes } from "react";

// A password field with a temporary eye toggle: the text is shown only while the eye is on, and each field starts hidden again.
export function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [shown, setShown] = useState(false);
  return (
    <div className="pwwrap">
      <input {...props} type={shown ? "text" : "password"} className={`field ${props.className ?? ""}`} autoCapitalize="none" spellCheck={false} />
      <button type="button" className="eye" aria-label={shown ? "Hide the text" : "Show the text"} aria-pressed={shown} onClick={() => setShown(!shown)}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {shown && <path d="M4 20 20 4" />}
        </svg>
      </button>
    </div>
  );
}
