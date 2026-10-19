// Layout check for docs/design/mockup.html. Run from frontend/: node scripts/mockup-check.mjs
// The same checks (side gaps, page scroll, equal section bottoms and heading tops, uniform scale) are reused against the real app.
import { chromium } from "@playwright/test";
const URL = "file:///G:/china%20competition/Budget_Kernel_Project_Starter/docs/design/mockup.html";
const screens = ["signin","mandate","ask","review","activity","attack","settings"];
const sizes = [[1366,768],[1920,1080],[2560,1440],[1024,768],[390,844]];
const b = await chromium.launch({ channel: "chrome" });
const fails = []; const scale = {};
for (const [w,h] of sizes) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  for (const s of screens) {
    await p.goto(`${URL}?screen=${s}`); await p.waitForTimeout(700);
    const r = await p.evaluate(() => {
      const de = document.documentElement, W = innerWidth, H = innerHeight;
      const frame = document.querySelector(".app, .signin");
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
