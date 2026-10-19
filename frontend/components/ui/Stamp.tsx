// A verdict word in a box. Colour marks the outcome, the word carries it too (never colour alone).
export type Tone = "ok" | "wait" | "no" | "dim";
export default function Stamp({ children }: { children: string }) {
  return <span className="stamp">{children}</span>;
}
