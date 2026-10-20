import { chromium } from "playwright";
const url = (s) => `file:///G:/china competition/Budget_Kernel_Project_Starter/docs/design/mockup.html?screen=${s}`;
const screens = ["signin","mandate","ask","review","activity","attack","settings"];
const b = await chromium.launch({ channel: "chrome" });
let bad = 0;
for (const w of [390, 360]) {
  const p = await b.newPage({ viewport: { width: w, height: 844 } });
  await p.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
  for (const s of screens) {
    await p.goto(url(s)); await p.waitForTimeout(300);
    const r = await p.evaluate(() => {
      const out = [];
      if (document.documentElement.scrollWidth > innerWidth) out.push("page scrolls sideways");
      document.querySelectorAll("*").forEach((e) => {
        const cs = getComputedStyle(e);
        if (cs.display === "none" || e.closest("svg")) return;
        const r = e.getBoundingClientRect();
        if (r.width && (r.right > innerWidth + 1 || r.left < -1)) out.push("outside: " + e.className + " " + (e.textContent||"").slice(0,30));
        if (e.scrollWidth > e.clientWidth + 1 && cs.overflow !== "visible" && !/ellipsis/.test(cs.textOverflow)) out.push("clipped x: " + e.className);
        if (e.scrollHeight > e.clientHeight + 1 && cs.overflowY !== "visible" && cs.overflowY !== "auto" && cs.overflowY !== "scroll" && !e.matches(".cheque")) out.push("clipped y: " + e.className);
      });
      // rows must not overlap the next row
      document.querySelectorAll(".row").forEach((e, i, a) => { const n = a[i+1]; if (n && n.parentElement === e.parentElement && e.getBoundingClientRect().bottom > n.getBoundingClientRect().top + 1) out.push("rows overlap"); });
      return [...new Set(out)];
    });
    if (r.length) { bad++; console.log(w, s, r.slice(0, 6)); }
    if (w === 390) await p.screenshot({ path: `../docs/design/_phone-${s}.png`, fullPage: true });
  }
  await p.close();
}
await b.close();
console.log(bad ? "CLIP PROBLEMS" : "PHONE OK");
