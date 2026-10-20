"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

// First-visit guide: a hand-drawn overlay that circles each tab and says what it is for. It goes away on a click,
// "Got it", Escape or any scroll, and it is remembered per role in this browser (only a "seen" flag is stored, never a key).
// A button in Settings brings it back. Plain text only; nothing here reads or changes any data.

export type Caption = { pre?: string; hl: string; post?: string };
export type TourStep = { selector: string; text: Caption; extra?: boolean };   // extra: a lone control, not one of the tab row

const SEEN = (kind: string) => `bk.tour.v1.${kind}`;
export const TOUR_EVENT = "bk:tour";

export function tourSeen(kind: string): boolean {
  try { return localStorage.getItem(SEEN(kind)) === "1"; } catch { return seenInMemory.has(kind); }
}
const seenInMemory = new Set<string>();
function markSeen(kind: string) {
  seenInMemory.add(kind);
  try { localStorage.setItem(SEEN(kind), "1"); } catch { /* private window: the memory set still stops a repeat this visit */ }
}

type Placed = { cx: number; cy: number; rx: number; ry: number; left: number; top: number; w: number; ax: number; ay: number; bx: number; by: number; text: Caption; i: number; bottom: boolean };

// A loose, slightly overshooting ellipse, so it reads as drawn by hand. Deterministic: the same shape on every render.
function ellipsePath(cx: number, cy: number, rx: number, ry: number, seed: number): string {
  const n = 56, pts: string[] = [];
  for (let k = 0; k <= n; k++) {
    const t = (k / n) * Math.PI * 2.16 - 0.5;
    const j = 1 + 0.035 * Math.sin(k * 0.9 + seed * 2.3) + 0.012 * (k / n);
    const x = cx + Math.cos(t) * rx * j, y = cy + Math.sin(t) * ry * j + (k / n) * 2;
    pts.push(`${k === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return pts.join(" ");
}

export default function Tour({ kind, steps }: { kind: string; steps: TourStep[] }) {
  const [open, setOpen] = useState(false);
  const [placed, setPlaced] = useState<Placed[]>([]);
  const [vp, setVp] = useState({ w: 0, h: 0 });
  const gotIt = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => { markSeen(kind); setOpen(false); }, [kind]);

  // Open once, on the first visit for this role; Settings can ask for it again.
  useEffect(() => {
    if (!tourSeen(kind)) { const id = setTimeout(() => setOpen(true), 700); return () => clearTimeout(id); }
  }, [kind]);
  useEffect(() => {
    const again = () => setOpen(true);
    window.addEventListener(TOUR_EVENT, again);
    return () => window.removeEventListener(TOUR_EVENT, again);
  }, []);

  const measure = useCallback(() => {
    const w = window.innerWidth, h = window.innerHeight;
    // A selector may match a tab on the desktop bar and on the phone bar; use whichever one is showing.
    const shown = (sel: string) => Array.from(document.querySelectorAll<HTMLElement>(sel)).find((el) => el.getBoundingClientRect().width > 0);
    const found = steps.map((s) => ({ s, el: shown(s.selector) })).filter((f) => f.el)
      .map((f) => ({ s: f.s, r: f.el!.getBoundingClientRect() }));
    if (!found.length) { setPlaced([]); return; }
    const low = (r: DOMRect) => r.top > h * 0.7;                              // phone: the tabs live in the bottom bar
    const centres = found.filter((f) => low(f.r) === low(found[0].r)).map((f) => f.r.left + f.r.width / 2).sort((a, b) => a - b);
    const gap = centres.length > 1 ? Math.min(...centres.slice(1).map((c, i) => c - centres[i]).filter((g) => g > 20), 240) : 240;
    const W = Math.max(110, Math.min(2.8 * gap, 190));
    const seen = { top: 0, bottom: 0 };
    const tabsOnTop = found.filter((f) => !low(f.r) && !f.s.extra);
    const spread = tabsOnTop.length > 2;                                       // desktop: fan the captions out under the bar
    const CW = 190, step = Math.min(140, (w - 16 - CW) / Math.max(1, tabsOnTop.length - 1));
    const left0 = Math.max(8, tabsOnTop.length ? tabsOnTop[0].r.left + tabsOnTop[0].r.width / 2 - CW / 2 : 8);
    let k = 0;
    const out: Placed[] = found.map((f, i) => {
      const r = f.r, cx = r.left + r.width / 2, cy = r.top + r.height / 2, bottom = low(r);
      const fan = spread && !bottom && !f.s.extra;
      const row = fan ? k % 3 : seen[bottom ? "bottom" : "top"]++ % 3;
      const Wc = fan ? CW : W;
      const left = fan ? Math.min(left0 + k++ * step, w - CW - 8) : Math.max(8, Math.min(cx - Wc / 2, w - Wc - 8));
      const top = bottom ? r.top - 74 - row * 66 : r.bottom + 46 + row * (fan ? 64 : 66);
      const ax = Math.max(left + 14, Math.min(fan ? left + Wc / 2 : cx, left + Wc - 14));
      const ry = Math.max(r.height / 2 + 6, 17);
      return { cx, cy, rx: r.width / 2 + 12, ry, left, top, w: Wc, ax, ay: bottom ? top + 60 : top - 6,
               bx: cx, by: bottom ? cy - ry - 2 : cy + ry + 2, text: f.s.text, i, bottom };
    });
    setVp({ w, h }); setPlaced(out);
  }, [steps]);

  useLayoutEffect(() => {
    if (!open) return;
    const first = requestAnimationFrame(measure);
    const retry = setTimeout(measure, 400);                                  // fonts and the first paint can move the tabs a little
    window.addEventListener("resize", measure);
    return () => { cancelAnimationFrame(first); clearTimeout(retry); window.removeEventListener("resize", measure); };
  }, [open, measure]);

  // Leave on Escape or on any scroll (capture phase, so a scroll inside a panel counts too).
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    const scrolled = () => close();
    window.addEventListener("keydown", esc);
    window.addEventListener("wheel", scrolled, { passive: true, capture: true });
    window.addEventListener("touchmove", scrolled, { passive: true, capture: true });
    window.addEventListener("scroll", scrolled, { passive: true, capture: true });
    gotIt.current?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener("keydown", esc);
      window.removeEventListener("wheel", scrolled, { capture: true });
      window.removeEventListener("touchmove", scrolled, { capture: true });
      window.removeEventListener("scroll", scrolled, { capture: true });
    };
  }, [open, close]);

  if (!open || !placed.length) return null;
  return (
    <div className="tour" role="dialog" aria-label="Quick guide to this screen" onClick={close}>
      <svg className="tour-svg" width={vp.w} height={vp.h} viewBox={`0 0 ${vp.w} ${vp.h}`} aria-hidden="true">
        <defs>
          <mask id="tour-holes">
            <rect width={vp.w} height={vp.h} fill="white" />
            {placed.map((p) => <ellipse key={p.i} cx={p.cx} cy={p.cy} rx={p.rx} ry={p.ry} fill="black" />)}
          </mask>
        </defs>
        <rect width={vp.w} height={vp.h} className="tour-dim" mask="url(#tour-holes)" />
        {placed.map((p) => {
          const dir = p.i % 2 ? -1 : 1;
          const mx = (p.ax + p.bx) / 2 + 26 * dir, my = (p.ay + p.by) / 2;
          const hx = p.bx, hy = p.by, ang = Math.atan2(hy - my, hx - mx), a = 8;
          const head = `M${hx + Math.cos(ang + 2.6) * a} ${hy + Math.sin(ang + 2.6) * a} L${hx} ${hy} L${hx + Math.cos(ang - 2.6) * a} ${hy + Math.sin(ang - 2.6) * a}`;
          return (
            <g key={p.i} style={{ ["--d" as string]: `${p.i * 110}ms` }}>
              <path className="tour-draw" pathLength={1} d={ellipsePath(p.cx, p.cy, p.rx, p.ry, p.i)} />
              <path className="tour-draw" pathLength={1} d={`M${p.ax} ${p.ay} Q${mx} ${my} ${hx} ${hy}`} />
              <path className="tour-draw" pathLength={1} d={head} />
            </g>
          );
        })}
      </svg>
      {placed.map((p) => (
        <p key={p.i} className="tour-cap" style={{ left: p.left, top: p.bottom ? undefined : p.top, bottom: p.bottom ? vp.h - p.top - 56 : undefined, width: p.w, ["--d" as string]: `${p.i * 110 + 250}ms` }}>
          {p.text.pre}<mark>{p.text.hl}</mark>{p.text.post}
        </p>
      ))}
      <div className="tour-foot">
        <button ref={gotIt} type="button" className="tour-ok" onClick={(e) => { e.stopPropagation(); close(); }}>Got it</button>
        <span>or click anywhere</span>
      </div>
    </div>
  );
}
