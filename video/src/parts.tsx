import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ARCHIVO, C, CAVEAT, sp, t } from "./tokens";

export const Paper: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: C.paper, fontFamily: ARCHIVO, color: C.ink }}>{children}</AbsoluteFill>
);

/** Fine sine-wave guilloché, the product's only texture. */
export const Guilloche: React.FC<{ w: number; h: number; opacity?: number }> = ({ w, h, opacity = 0.08 }) => {
  const lines = Array.from({ length: 14 }, (_, i) => {
    const pts: string[] = [];
    for (let x = 0; x <= w; x += 8) {
      const y = h / 2 + Math.sin(x / 38 + i * 0.45) * (h * 0.32) * Math.cos(x / 210 + i * 0.2);
      pts.push(`${x === 0 ? "M" : "L"}${x} ${y.toFixed(1)}`);
    }
    return <path key={i} d={pts.join(" ")} fill="none" stroke={C.ink} strokeWidth={1} />;
  });
  return <svg width={w} height={h} style={{ position: "absolute", inset: 0, opacity }}>{lines}</svg>;
};

/** Heading in the display width. */
export const Display: React.FC<{ size?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ size = 72, children, style }) => (
  <div style={{ fontFamily: ARCHIVO, fontWeight: 700, fontStretch: "125%", fontVariationSettings: "'wdth' 125", fontSize: size, lineHeight: 1.05, letterSpacing: -0.5, ...style }}>{children}</div>
);

/** Words that write on one by one from frame `at`, `gap` frames apart. */
export const WordsOn: React.FC<{ text: string; at: number; gap?: number; style?: React.CSSProperties }> = ({ text, at, gap = 5, style }) => {
  const f = useCurrentFrame();
  return (
    <span style={style}>
      {text.split(" ").map((w, i) => {
        const k = t(f, at + i * gap, at + i * gap + 10);
        return <span key={i} style={{ opacity: k, display: "inline-block", transform: `translateY(${(1 - k) * 14}px)`, marginRight: "0.25em" }}>{w}</span>;
      })}
    </span>
  );
};

/** Characters typed from frame `at`, 2 frames per character, with a blinking cursor. */
export const Typed: React.FC<{ text: string; at: number; cps?: number; style?: React.CSSProperties; cursor?: boolean }> = ({ text, at, cps = 2, style, cursor = true }) => {
  const f = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor((f - at) / cps)));
  const blink = Math.floor(f / 15) % 2 === 0;
  return <span style={style}>{text.slice(0, n)}{cursor && <span style={{ opacity: blink ? 1 : 0, borderLeft: `3px solid ${C.ink}`, marginLeft: 2 }}>&nbsp;</span>}</span>;
};

export type StampKind = "Approved" | "Held" | "Refused" | "Released";
const STAMP: Record<StampKind, string> = { Approved: C.approve, Held: C.held, Refused: C.refuse, Released: C.ink2 };

/** A rubber stamp landing: scale 1.08 -> 1, rotation -4 -> -2 degrees, ink spreading. No bounce. */
export const Stamp: React.FC<{ kind: StampKind; at: number; size?: number; style?: React.CSSProperties }> = ({ kind, at, size = 44, style }) => {
  const f = useCurrentFrame();
  if (f < at) return null;
  const k = Math.min(1, (f - at) / 6);
  const col = STAMP[kind];
  return (
    <div style={{
      display: "inline-block", border: `${1 + 3 * k}px solid ${col}`, color: col, padding: `${size * 0.12}px ${size * 0.4}px`,
      fontFamily: ARCHIVO, fontWeight: 800, fontSize: size, fontStretch: "125%", fontVariationSettings: "'wdth' 125",
      transform: `scale(${1.08 - 0.08 * k}) rotate(${-4 + 2 * k}deg)`, opacity: Math.min(1, (f - at) / 2), background: "rgba(251,251,248,0.92)", ...style,
    }}>{kind}</div>
  );
};

/** The proposal slip (dashed, untrusted) or verdict slip (solid). */
export const Slip: React.FC<{ lines: string[]; solid?: boolean; w?: number; tag?: string; style?: React.CSSProperties; children?: React.ReactNode }> = ({ lines, solid, w = 360, tag, style, children }) => (
  <div style={{ width: w, background: C.sheet, border: `3px ${solid ? "solid" : "dashed"} ${solid ? C.ink : C.ink2}`, padding: "22px 26px", position: "relative", ...style }}>
    {tag && <div style={{ fontSize: 24, color: C.muted, marginBottom: 10 }}>{tag}</div>}
    {lines.map((l, i) => <div key={i} style={{ fontSize: 34, lineHeight: 1.35, fontVariantNumeric: "tabular-nums" }}>{l}</div>)}
    {children}
  </div>
);

/** Budget bar: free part, reserved hatch. Values in the same unit as `total`. */
export const BudgetBar: React.FC<{ total: number; used: number; w: number; h?: number; color?: string; label?: React.ReactNode; overflow?: number }> = ({ total, used, w, h = 34, color = C.ink, label, overflow = 0 }) => (
  <div style={{ width: w }}>
    {label && <div style={{ fontSize: 30, marginBottom: 12, fontVariantNumeric: "tabular-nums" }}>{label}</div>}
    <div style={{ position: "relative", width: w, height: h, border: `2px solid ${C.ink}`, background: C.sheet }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: Math.min(used / total, 1) * (w - 4), background: color }} />
      {overflow > 0 && <div style={{ position: "absolute", left: w - 4, top: -2, bottom: -2, width: overflow, background: C.refuse }} />}
    </div>
  </div>
);

/** Browser frame around a real screenshot, with a slow push-in. */
export const BrowserFrame: React.FC<{ src: string; w?: number; push?: number; from?: number; dur?: number; children?: React.ReactNode; style?: React.CSSProperties; blur?: { x: number; y: number; w: number; h: number } }> = ({ src, w = 1600, push = 0.03, from = 0, dur = 300, children, style, blur }) => {
  const f = useCurrentFrame();
  const h = w * 0.625;
  const s = 1 + push * interpolate(f, [from, from + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ width: w, background: C.sheet, border: `2px solid ${C.ink}`, boxShadow: "0 18px 50px rgba(23,32,28,0.12)", ...style }}>
      <div style={{ height: 44, borderBottom: `1px solid ${C.rule}`, display: "flex", alignItems: "center", gap: 10, padding: "0 18px" }}>
        {[0, 1, 2].map((i) => <span key={i} style={{ width: 12, height: 12, borderRadius: 6, border: `1.5px solid ${C.muted}` }} />)}
        <span style={{ marginLeft: 18, fontSize: 20, color: C.muted }}>budget-kernel (testnet demo)</span>
      </div>
      <div style={{ position: "relative", width: w, height: h, overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, transform: `scale(${s})`, transformOrigin: "50% 40%" }}>
          <Img src={staticFile(`screens/${src}`)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }} />
          {blur && <div style={{ position: "absolute", left: `${blur.x * 100}%`, top: `${blur.y * 100}%`, width: `${blur.w * 100}%`, height: `${blur.h * 100}%`, backdropFilter: "blur(7px)", background: "rgba(251,251,248,0.35)" }} />}
          {children}
        </div>
      </div>
    </div>
  );
};

/** Hand-drawn ellipse that draws on from frame `at` (positions in px inside its parent). */
export const HandCircle: React.FC<{ x: number; y: number; rx: number; ry: number; at: number; color?: string; seed?: number }> = ({ x, y, rx, ry, at, color = C.refuse, seed = 1 }) => {
  const f = useCurrentFrame();
  const k = t(f, at, at + 16);
  if (k <= 0) return null;
  const pts: string[] = [];
  const n = 60;
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * Math.PI * 2.15 - 0.6;
    const j = 1 + 0.04 * Math.sin(i * 0.8 + seed);
    pts.push(`${i ? "L" : "M"}${(x + Math.cos(a) * rx * j).toFixed(1)} ${(y + Math.sin(a) * ry * j + i * 0.05).toFixed(1)}`);
  }
  return (
    <svg style={{ position: "absolute", inset: 0, overflow: "visible", pointerEvents: "none" }} width="100%" height="100%">
      <path d={pts.join(" ")} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - k} />
    </svg>
  );
};

/** Handwritten note with one highlighted word. */
export const HandNote: React.FC<{ pre?: string; hl: string; post?: string; at: number; style?: React.CSSProperties }> = ({ pre = "", hl, post = "", at, style }) => {
  const f = useCurrentFrame();
  const k = t(f, at, at + 12);
  return (
    <div style={{ position: "absolute", fontFamily: CAVEAT, fontWeight: 700, fontSize: 46, color: C.ink, opacity: k, transform: `translateY(${(1 - k) * 10}px)`, ...style }}>
      {pre}<span style={{ background: C.marker, padding: "0 10px", borderRadius: 6 }}>{hl}</span>{post}
    </div>
  );
};

/** Mouse cursor travelling along a gentle arc between waypoints [frame, x, y]; click rings at the given frames. */
export const Cursor: React.FC<{ path: [number, number, number][]; clicks?: number[] }> = ({ path, clicks = [] }) => {
  const f = useCurrentFrame();
  let x = path[0][1], y = path[0][2];
  for (let i = 1; i < path.length; i++) {
    const [f0, x0, y0] = path[i - 1], [f1, x1, y1] = path[i];
    if (f >= f0) {
      const k = t(f, f0, f1);
      x = x0 + (x1 - x0) * k;
      y = y0 + (y1 - y0) * k - Math.sin(k * Math.PI) * 40;
    }
  }
  return (
    <>
      {clicks.map((c) => {
        const k = (f - c) / 10;
        if (k < 0 || k > 1) return null;
        return <div key={c} style={{ position: "absolute", left: x - 30 * k - 6, top: y - 30 * k - 6, width: 60 * k + 12, height: 60 * k + 12, borderRadius: "50%", border: `3px solid ${C.ink}`, opacity: 1 - k }} />;
      })}
      <svg style={{ position: "absolute", left: x, top: y }} width="34" height="44" viewBox="0 0 17 22">
        <path d="M1 1 L1 17 L5 13 L8 20 L11 19 L8 12 L14 12 Z" fill={C.sheet} stroke={C.ink} strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </>
  );
};

/** Draw-on line (SVG) from frame `at`. */
export const DrawLine: React.FC<{ d: string; at: number; dur?: number; color?: string; width?: number }> = ({ d, at, dur = 16, color = C.ink, width = 3 }) => {
  const f = useCurrentFrame();
  const k = t(f, at, at + dur);
  return <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - k} />;
};

/** Fade/slide-in wrapper for an element entering at `at`. */
export const In: React.FC<{ at: number; dy?: number; dx?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at, dy = 24, dx = 0, children, style }) => {
  const f = useCurrentFrame();
  const k = sp(f, at);
  return <div style={{ opacity: Math.min(1, k * 1.4), transform: `translate(${(1 - k) * dx}px, ${(1 - k) * dy}px)`, ...style }}>{children}</div>;
};
