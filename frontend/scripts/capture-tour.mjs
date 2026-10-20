// Screenshots of the first-visit guide (owner, agent, phone) into docs/submission/screenshots/r3. Run from frontend/ on a seeded demo.
import { chromium } from "@playwright/test";
const OUT = "../docs/submission/screenshots/r3";
const b = await chromium.launch({ channel: "chrome" });
async function tour(who, vp, name) {
  const p = await b.newPage({ viewport: vp });
  await p.goto("http://localhost:3000");
  await p.getByRole("button", { name: new RegExp(`Continue as ${who}`) }).click();
  await p.locator(".tour").waitFor({ timeout: 90000 });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: `${OUT}/${name}.png` });
  await p.close();
}
await tour("Nabil", { width: 1280, height: 800 }, "15-tour-owner");
await tour("Research bot", { width: 1280, height: 800 }, "16-tour-agent");
await tour("Nabil", { width: 390, height: 844 }, "17-tour-phone");
await b.close();
console.log("saved 15 to 17");
