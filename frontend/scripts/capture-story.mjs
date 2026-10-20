import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
const OUT = "../docs/submission/screenshots/r3";
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch({ channel: "chrome" });
const D = { width: 1280, height: 800 }, P = { width: 390, height: 844 };
const shot = (p, n) => p.screenshot({ path: `${OUT}/${n}.png` });
const log = (m) => console.log(m);

async function signIn(p, who) {
  await p.goto("http://localhost:3000");
  await p.getByRole("button", { name: new RegExp(`Continue as ${who}`) }).click();
  await p.locator(".app").waitFor({ timeout: 60000 });
  await p.getByText("Who may spend").waitFor({ timeout: 90000 });
}
const tab = (p, name) => p.locator("nav.tabs a, nav.bottom a", { hasText: name }).filter({ visible: true }).first().click();

// --- agent already asked and was suspended in the previous run; show what the agent sees now
const a = await b.newPage({ viewport: D });
await a.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
await signIn(a, "Research bot");
await tab(a, "Ask"); await a.waitForTimeout(3000); await shot(a, "06-ask-suspended"); log("suspended view");
await a.close();

// --- owner
const o = await b.newPage({ viewport: D });
await o.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
await signIn(o, "Nabil");
await o.waitForTimeout(8000); await shot(o, "02-mandate");
await o.getByRole("button", { name: /Manage Research bot/ }).click(); await o.waitForTimeout(800); await shot(o, "09-owner-reinstate");
await tab(o, "Review"); await o.getByText("Waiting for you").waitFor(); await o.waitForTimeout(6000); await shot(o, "07-review");
await tab(o, "Activity"); await o.waitForTimeout(8000); await shot(o, "08-activity");
await tab(o, "Attack"); await o.waitForTimeout(3000);
await o.getByRole("button", { name: /Run all attacks/ }).click();
await o.getByText(/Held/).first().waitFor({ timeout: 600000 }).catch(() => log("attack wait timeout"));
for (let i = 0; i < 60; i++) { // wait until no row says "Running"
  const n = await o.getByText(/Running|\d of 7/).count(); if (!n) break; await o.waitForTimeout(5000);
}
await shot(o, "10-attack-lab"); log("attacks");
await tab(o, "Settings"); await o.waitForTimeout(2000); await shot(o, "11-settings");
await o.close();

// --- manager sees the owner-only reinstate text
const m = await b.newPage({ viewport: D });
await m.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
await signIn(m, "Ops bot");
await m.waitForTimeout(6000);
await m.getByRole("button", { name: /Manage Research bot/ }).click(); await m.waitForTimeout(800); await shot(m, "12-manager-owner-only");
await m.close();

// --- phone
const ph = await b.newPage({ viewport: P });
await ph.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
await signIn(ph, "Nabil"); await ph.waitForTimeout(8000); await shot(ph, "13-phone-mandate");
await tab(ph, "Review"); await ph.waitForTimeout(6000); await shot(ph, "14-phone-review");
await ph.close();
await b.close();
log("done");
