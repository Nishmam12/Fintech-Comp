// End-to-end check of the real sign-in and setup through the UI (dev server :3000, API :8000 with BK_ALLOW_SIGNUP=1).
// Run from frontend/: node scripts/login-check.mjs   (npm run check:login). Creates one throwaway account per run.
// Story: wrong password is refused -> the demo owner signs in with username and password -> a new person creates an account ->
// setup (mandate, agent with a one-time key, budget) -> dashboard -> sign out -> sign back in -> change password ->
// old password refused, new one works. Prints one line per step and "LOGIN OK"; never prints a password or key.
import { chromium } from "@playwright/test";

const URL = process.env.APP_URL ?? "http://localhost:3000";
const OWNER = { user: "nabil", pass: process.env.BK_DEMO_PASSWORD ?? "kernel-demo-2026" };
const tag = Math.random().toString(36).slice(2, 8);
const ME = { name: "Login Tester", user: `tester.${tag}`, pass: "an easy to type passphrase", next: "a different passphrase 42" };

const b = await chromium.launch({ channel: "chrome" });
const fails = [];
const step = (name, ok, extra = "") => { console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? `  (${extra})` : ""}`); if (!ok) fails.push(name); };
const seen = (p, text, ms = 120000) => p.getByText(text).first().waitFor({ timeout: ms }).then(() => true, () => false);

async function fresh() {
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto(URL);
  await p.getByLabel("Username").waitFor({ timeout: 60000 });
  return p;
}
async function signIn(p, user, pass) {
  await p.getByLabel("Username").fill(user);
  await p.getByLabel("Password", { exact: true }).fill(pass);
  await p.getByRole("button", { name: "Sign in", exact: true }).click();
}

// 1. wrong password
let p = await fresh();
await signIn(p, OWNER.user, "definitely not the password");
step("wrong password is refused in plain words", await seen(p, "Wrong username or password", 60000));
step("the same message for a username that does not exist", await (async () => {
  await p.getByLabel("Username").fill("nobody.here.at.all"); await p.getByRole("button", { name: "Sign in", exact: true }).click();
  await p.waitForTimeout(3000); return (await p.getByText("Wrong username or password").count()) > 0;
})());

// 2. the demo owner, with a password
await p.getByLabel("Username").fill(OWNER.user);
await p.getByLabel("Password", { exact: true }).fill(OWNER.pass);
await p.getByRole("button", { name: "Sign in", exact: true }).click();
step("demo owner signs in with username and password", await seen(p, "Who may spend"));
await p.locator("nav.tabs a", { hasText: "Settings" }).click();
step("a password account sees Change password, not key rotation", await seen(p, "Your password", 60000) && (await p.getByText("Rotate key").count()) === 0);
await p.close();

// 3. a new person creates an account
p = await fresh();
await p.getByRole("tab", { name: "Create account" }).click();
await p.getByLabel("Your name").fill(ME.name);
await p.getByLabel("Username").fill(ME.user);
await p.getByLabel("Password", { exact: true }).fill(ME.pass);
await p.getByLabel("Repeat the password").fill(ME.pass + "x");
await p.getByRole("button", { name: "Create account", exact: true }).click();
step("mismatched passwords are caught before anything is sent", await seen(p, "not the same", 10000));
await p.getByLabel("Repeat the password").fill(ME.pass);
await p.getByRole("button", { name: "Create account", exact: true }).click();
step("a new account lands on setup (no mandate yet)", await seen(p, "1. Fund a mandate"));

// 4. setup
await p.getByRole("button", { name: "Create the mandate" }).click();
step("setup: the mandate is created", await seen(p, "never spendable"));
await p.getByLabel("New agent name").fill("Research bot");
await p.getByRole("button", { name: "Add agent" }).click();
const keyShown = await seen(p, "Its API key is shown once");
step("setup: the agent's key is shown once", keyShown && (await p.locator(".serial", { hasText: /^bk_/ }).count()) === 1);
await p.getByRole("button", { name: "I have stored it" }).click();
step("setup: the key is gone after 'I have stored it'", (await p.locator(".serial", { hasText: /^bk_/ }).count()) === 0);
await p.getByRole("button", { name: "Give this agent a budget" }).click();
step("setup: the agent gets a budget", await seen(p, "300.00 USD", 60000));
await p.getByRole("button", { name: "Open the dashboard" }).click();
step("setup: the dashboard opens on the new mandate", await seen(p, "Who may spend") && await seen(p, "1,000.00"));
step("the new mandate shows the agent with its budget", await seen(p, "Research bot", 30000));

// 5. sign out and back in
await p.getByText("Sign out").first().click();
await p.getByLabel("Username").waitFor({ timeout: 30000 });
await signIn(p, ME.user, ME.pass);
step("signing back in goes straight to the mandate", await seen(p, "Who may spend"));

// 6. change the password
await p.locator("nav.tabs a", { hasText: "Settings" }).click();
await p.getByLabel("Current password").fill(ME.pass);
await p.getByLabel("New password (at least 10 characters)").fill(ME.next);
await p.getByLabel("Repeat the new password").fill(ME.next);
await p.getByRole("button", { name: "Change password" }).click();
step("the password is changed", await seen(p, "Password changed", 60000));
await p.getByText("Sign out").first().click();
await p.getByLabel("Username").waitFor({ timeout: 30000 });
await signIn(p, ME.user, ME.pass);
step("the old password no longer works", await seen(p, "Wrong username or password", 60000));
await p.getByLabel("Password", { exact: true }).fill(ME.next);
await p.getByRole("button", { name: "Sign in", exact: true }).click();
step("the new password works", await seen(p, "Who may spend"));
await p.close();

await b.close();
console.log(fails.length ? `LOGIN FAILED: ${fails.join("; ")}` : "LOGIN OK");
process.exit(fails.length ? 1 : 0);
