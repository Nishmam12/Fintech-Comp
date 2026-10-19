// The one section module (UI_SPEC revision 3): a 3.5rem heading on an ink rule, a body that fills and scrolls, an optional foot.
// `span` is the column count out of 12 (12, 8, 6 or 4); sections in a row all end at the bottom of the screen.
import type { ReactNode } from "react";

export default function Section({
  span, title, meta, head, foot, className = "", live, children,
}: {
  span: 12 | 8 | 6 | 4;
  title: string;
  meta?: ReactNode;
  head?: ReactNode;        // rows pinned under the heading (column headers)
  foot?: ReactNode;
  className?: string;
  live?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={`c${span} sec ${className}`} aria-live={live ? "polite" : undefined}>
      <div className="sec-head"><h2 className="fig">{title}</h2>{meta !== undefined && <span className="meta">{meta}</span>}</div>
      {head}
      <div className="sec-body">{children}</div>
      {foot && <div className="sec-foot">{foot}</div>}
    </section>
  );
}

// Ruled-ledger filler: empty space is drawn as empty rows, with one plain sentence in the first.
export function Filler({ children }: { children?: ReactNode }) {
  return <div className="filler">{children && <p>{children}</p>}</div>;
}
