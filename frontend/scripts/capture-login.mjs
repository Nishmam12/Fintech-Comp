// Screenshots of the login screens added on 2026-10-20 (sign-in, create account, setup, change password).
// Run from frontend/ with the API (BK_ALLOW_SIGNUP=1) and the dev server up. Uses a throwaway account; touches no demo data.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
const OUT = "../docs/submission/screenshots/r3";
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch({ channel: "chrome" });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
await p.addInitScript(() => { try { localStorage.setItem("bk.tour.v1.owner", "1"); localStorage.setItem("bk.tour.v1.holder", "1"); } catch {} });
const shot = (n) => p.screenshot({ path: `${OUT}/${n}.png` });
const user = `shots.${Date.now().toString(36)}@example.com`, pass = "a calm demo passphrase";

await p.goto("http://localhost:3000");
await p.getByRole("tab", { name: "Sign in" }).waitFor({ timeout: 60000 });
await shot("01-signin");
await p.getByRole("tab", { name: "Create account" }).click();
await p.getByLabel("Your name").fill("Mei Chen");
await p.getByLabel("Username").fill(user);
await p.getByLabel("Password", { exact: true }).fill(pass);
await p.getByLabel("Repeat the password").fill(pass);
await shot("01b-create-account");
await p.getByRole("button", { name: "Create account", exact: true }).click();
await p.getByRole("button", { name: "Create the mandate" }).waitFor({ timeout: 90000 });
await shot("01c-setup");
await p.getByRole("button", { name: "Create the mandate" }).click();
await p.getByRole("button", { name: "Add agent" }).waitFor({ timeout: 90000 });
await p.locator("input").last().fill("Research bot");
await p.getByRole("button", { name: "Add agent" }).click();
await p.getByRole("button", { name: "Copy the key" }).waitFor({ timeout: 90000 });
await shot("01d-setup-agent-key");
await p.getByRole("button", { name: "I have stored it" }).click();
await p.getByRole("button", { name: "Give this agent a budget" }).waitFor({ timeout: 30000 });
await shot("01e-setup-budget");
await b.close();
console.log("saved 01, 01b to 01e to docs/submission/screenshots/r3");
