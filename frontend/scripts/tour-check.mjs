// The first-visit guide (components/Tour.tsx): shown once per role in a fresh browser, closed by a scroll, not shown again after a
// reload, brought back by "Show the guide again" in Settings, closed by a click. Dev server :3000, demo seeded. Prints "TOUR OK".
import { chromium } from "@playwright/test";
const URL = process.env.APP_URL ?? "http://localhost:3000";
const b = await chromium.launch({ channel: "chrome" });
const fails = [];
const step = (n, ok) => { console.log(`${ok ? "ok  " : "FAIL"} ${n}`); if (!ok) fails.push(n); };
const shown = async (p, ms = 15000) => p.locator(".tour").waitFor({ timeout: ms }).then(() => true, () => false);
const gone = async (p) => p.locator(".tour").waitFor({ state: "detached", timeout: 5000 }).then(() => true, () => false);

const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });
let p = await ctx.newPage();
await p.goto(URL);
await p.getByRole("button", { name: /Continue as Nabil/ }).click();
step("owner: the guide opens on the first visit", await shown(p, 90000));
step("it names every owner tab and sign out", (await p.locator(".tour-cap").count()) === 6);
await p.mouse.wheel(0, 300);
step("a scroll closes it", await gone(p));
await p.reload();
await p.getByRole("button", { name: /Continue as Nabil/ }).click();
await p.locator(".app").waitFor({ timeout: 90000 });
step("it does not come back after a reload", !(await shown(p, 4000)));
await p.locator("nav.tabs a", { hasText: "Settings" }).click();
await p.getByRole("button", { name: "Show the guide again" }).click();
step("Settings brings it back", await shown(p, 5000));
await p.mouse.click(640, 500);
step("a click anywhere closes it", await gone(p));
await p.close();

p = await ctx.newPage();
await p.goto(URL);
await p.getByRole("button", { name: /Continue as Research bot/ }).click();
step("agent: its own first visit shows the guide (separate flag)", await shown(p, 90000));
step("it names the agent's tabs (4) and sign out", (await p.locator(".tour-cap").count()) === 5);
await p.keyboard.press("Escape");
step("Escape closes it", await gone(p));
await b.close();
console.log(fails.length ? `TOUR FAILED: ${fails.join("; ")}` : "TOUR OK");
process.exit(fails.length ? 1 : 0);
