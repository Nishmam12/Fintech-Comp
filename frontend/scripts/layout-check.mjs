// Layout check for the real app (dev server on :3000, API on :8000, demo accounts seeded by scripts/demo_seed.py).
// Run from frontend/: node scripts/layout-check.mjs. Same checks as mockup-check.mjs: no side gaps, no page scroll on desktop,
// equal section bottoms and heading tops, uniform scale. Prints failures only; never prints a key.
import { chromium } from "@playwright/test";
const URL = process.env.APP_URL ?? "http://localhost:3000";
// [screen, demo account to sign in as, tab to click (null = landing screen)]
const screens = [["signin", null, null], ["mandate", "Nabil", null], ["review", "Nabil", "Review"], ["activity", "Nabil", "Activity"],
  ["attack", "Nabil", "Attack lab"], ["settings", "Nabil", "Settings"], ["ask", "Research bot", "Ask"]];
const sizes = [[1366,768],[1920,1080],[2560,1440],[1024,768],[390,844]];
const b = await chromium.launch({ channel: "chrome" });
const fails = []; const scale = {};
for (const [w,h] of sizes) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
  for (const [s, who, tab] of screens) {
    await p.goto(URL); await p.waitForTimeout(500);
    if (who) {
      await p.getByRole("button", { name: new RegExp(`Continue as ${who}`) }).first().click(); await p.waitForTimeout(1200);
      if (tab) { await p.locator(w >= 768 ? "nav.tabs a" : "nav.bottom a", { hasText: tab.replace("Attack lab", w >= 768 ? "Attack lab" : "Attack") }).first().click(); await p.waitForTimeout(1200); }
    }
    const r = await p.evaluate(() => {
      const de = document.documentElement, W = innerWidth, H = innerHeight;
      const frame = document.querySelector(".app, .signin");
      if (!frame) return { missing: true };
      const fr = frame.getBoundingClientRect();
      const main = document.querySelector(".main");
      const mr = main ? main.getBoundingClientRect() : null;
      const secs = [...document.querySelectorAll(".main > .sec, .signin > section")].map(e => e.getBoundingClientRect());
      const heads = [...document.querySelectorAll(".main > .sec .sec-head")].map(e => Math.round(e.getBoundingClientRect().top));
      const q = (sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return { w: r.width / W, h: r.height / W, f: parseFloat(getComputedStyle(e).fontSize) / W }; };
      return { W, H, left: fr.left, right: fr.right, sw: de.scrollWidth, sh: de.scrollHeight, mainBottom: mr && mr.bottom,
               secBottoms: secs.map(r => Math.round(r.bottom)), secTops: secs.map(r => Math.round(r.top)), heads,
               lm: { amount: q(".amount"), row: q(".row"), head: q(".sec-head"), stamp: q(".stamp") } };
    });
    const tag = `${s}@${w}x${h}`;
    if (r.missing) { fails.push(`${tag} frame not found (sign-in failed?)`); continue; }
    if (Math.abs(r.left) > 0.5 || Math.abs(r.right - r.W) > 0.5) fails.push(`${tag} side gap: ${r.left}..${r.right} of ${r.W}`);
    if (r.sw > r.W) fails.push(`${tag} horizontal scroll ${r.sw} > ${r.W}`);
    if (w >= 1024) {
      if (r.sh > r.H + 1) fails.push(`${tag} page scrolls vertically (${r.sh} > ${r.H})`);
      if (r.mainBottom !== null) { const pad = 0; const bottoms = r.secBottoms; const mn = Math.min(...bottoms), mx = Math.max(...bottoms);
        if (mx - mn > 1) fails.push(`${tag} section bottoms differ: ${bottoms}`);
      }
      // two halves in the same row share heading tops
      if (r.heads.length >= 2) { const tops = r.heads.slice(-2); if (r.secTops.length >= 2 && Math.abs(tops[0] - tops[1]) > 1) fails.push(`${tag} heading tops differ: ${tops}`); }
    }
    if (w >= 1366 && w <= 2560) (scale[s] ||= {})[w] = r.lm;
  }
  await p.close();
}
// uniform scale 1920 vs 2560 and 1366 vs 1920: ratio of size/innerWidth should match within 2%
for (const s of Object.keys(scale)) for (const [a,c] of [[1366,1920],[1920,2560]]) for (const k of ["amount","row","head","stamp"]) {
  const A = scale[s][a]?.[k], C = scale[s][c]?.[k]; if (!A || !C) continue;
  for (const m of ["w","h","f"]) { const d = Math.abs(A[m] - C[m]) / (A[m] || 1); if (d > 0.02 && !(m==="w" && k!=="amount")) fails.push(`${s} ${k}.${m} ${a}->${c} drift ${(d*100).toFixed(1)}%`); }
}
console.log(fails.length ? fails.join("\n") : "ALL CHECKS PASS");
await b.close();
