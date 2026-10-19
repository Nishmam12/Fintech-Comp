// A proposal (dashed slip: what the untrusted model read) paired with the kernel's verdict (stamped box). Equal widths.
import type { ReactNode } from "react";
import Stamp, { type Tone } from "@/components/ui/Stamp";

export default function ProposalVerdict({
  who, proposal, stamp, tone, reason, title,
}: { who: string; proposal: ReactNode; stamp: string; tone: Tone; reason: ReactNode; title?: string }) {
  return (
    <div className="row pairrow" title={title}>
      <div className="slip proposal"><small>{who}</small><span>{proposal}</span></div>
      <span className="arrow" aria-hidden="true">→</span>
      <div className={`slip verdict ${tone}`}><Stamp>{stamp}</Stamp><p>{reason}</p></div>
    </div>
  );
}
