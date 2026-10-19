// The history seal: green when the hash chain checks out, red when it does not.
export default function Seal({ ok = true }: { ok?: boolean }) {
  const c = ok ? "var(--approve)" : "var(--refuse)";
  return (
    <svg className="seal" viewBox="0 0 56 56" aria-hidden="true">
      <circle cx="28" cy="28" r="26" fill="none" stroke={c} strokeWidth="2" />
      <circle cx="28" cy="28" r="20" fill="none" stroke={c} strokeWidth="1" strokeDasharray="2 3" />
      {ok ? <path d="M18 29l7 7 13-15" fill="none" stroke={c} strokeWidth="3" /> : <path d="M19 19l18 18M37 19L19 37" fill="none" stroke={c} strokeWidth="3" />}
    </svg>
  );
}
