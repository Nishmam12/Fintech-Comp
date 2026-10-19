// A cheque face: paper with a guilloché pattern behind its content. Deterministic, no randomness, so server and client agree.
import type { ReactNode } from "react";

const W = 1200, H = 400;
const PATHS = Array.from({ length: 26 }, (_, k) => {
  let d = "";
  for (let x = 0; x <= W; x += 8) {
    const y = H / 2 + Math.sin(x / 70 + k * 0.24) * (70 + 50 * Math.sin(x / 260 + k * 0.5)) + Math.sin(x / 23 + k) * 6;
    d += `${x ? "L" : "M"}${x} ${y.toFixed(1)}`;
  }
  return d;
});

export function Guilloche() {
  return (
    <svg className="guilloche" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      {PATHS.map((d, k) => (
        <path key={k} d={d} fill="none" stroke={k % 2 ? "#c9d3c6" : "#d8dfd2"} strokeWidth="0.8" vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  );
}

export default function Cheque({ className = "", inner = "", children }: { className?: string; inner?: string; children: ReactNode }) {
  return (
    <section className={`cheque ${className}`}>
      <Guilloche />
      <div className={`cheque-in ${inner}`}>{children}</div>
    </section>
  );
}
