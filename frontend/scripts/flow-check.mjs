// Functional end-to-end check of the demo story through the real UI (dev server :3000, API :8000, freshly seeded demo mandate).
// Run from frontend/: node scripts/flow-check.mjs   (npm run check:flow). It CHANGES the demo mandate (use demo_seed.py first, and again after).
// Story: agent asks (approved, held, refused) -> owner approves the held one -> agent probes until suspended ->
// the agent can no longer ask -> a manager is told only the owner can reinstate -> owner reinstates -> agent can ask again ->
// owner revokes the manager -> the agent below is cut off. Prints one line per step and "FLOW OK", never a key.
import { chromium } from "@playwright/test";

const URL = process.env.APP_URL ?? "http://localhost:3000";
const b = await chromium.launch({ channel: "chrome" });
const fails = [];
const step = (name, ok, extra = "") => { console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? `  (${extra})` : ""}`); if (!ok) fails.push(name); };

async function open(who) {
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.goto(URL);
  await p.getByRole("button", { name: new RegExp(`Continue as ${who}`) }).click();
  await p.getByText("Who may spend").waitFor({ timeout: 120000 });
  return p;
}
const tab = (p, name) => p.locator("nav.tabs a", { hasText: name }).first().click();
async function ask(p, text) {
  await p.locator("#ask-text").fill(text);
  await p.getByRole("button", { name: /Send to the kernel/ }).click();
  const stamp = p.locator(".pair .verdict .stamp").first();
  await stamp.waitFor({ timeout: 120000 });
  const consequence = await p.locator(".consequence").innerText();
  return { stamp: (await stamp.innerText()).trim(), consequence };
}

// 1. agent
const a = await open("Research bot");
await tab(a, "Ask");
let r = await ask(a, "pay 20 USD to aws for cloud");   step("agent: 20 USD is approved", r.stamp === "Approved", r.stamp);
r = await ask(a, "pay 80 USD to aws for cloud");       step("agent: 80 USD is held for the owner", r.stamp === "Held", r.stamp);
r = await ask(a, "pay 150 USD to aws for cloud");      step("agent: 150 USD is refused, nothing reserved", r.stamp === "Refused" && /Nothing was reserved/.test(r.consequence), r.stamp);

// 2. owner approves the held request
const o = await open("Nabil");
await tab(o, "Review");
await o.getByText("Waiting for you").waitFor();
await o.getByRole("button", { name: "Approve" }).first().waitFor({ timeout: 60000 });
step("owner: the held request is in Review", true);
await o.getByRole("button", { name: "Approve" }).first().click();
await o.getByText(/Nothing is waiting for you/).waitFor({ timeout: 120000 }).then(() => step("owner: approving empties the inbox", true), () => step("owner: approving empties the inbox", false));

// 3. agent probes until the breaker trips
let last;
for (let i = 0; i < 4; i++) last = await ask(a, "pay 150 USD to aws for cloud");
step("agent: the fifth refusal suspends the grant", /suspended the grant/.test(last.consequence), last.consequence.slice(0, 60));
await a.reload(); await a.getByRole("button", { name: /Continue as Research bot/ }).click(); await a.getByText("Who may spend").waitFor({ timeout: 120000 });
await tab(a, "Ask");
await a.getByText(/do not hold an active grant/).waitFor({ timeout: 60000 }).then(() => step("agent: a suspended grant cannot ask", true), () => step("agent: a suspended grant cannot ask", false));

// 4. manager sees owner-only text
const m = await open("Ops bot");
await m.getByRole("button", { name: /Manage Research bot/ }).click();
await m.getByText(/Only the mandate owner can reinstate/).waitFor({ timeout: 60000 }).then(() => step("manager: told only the owner can reinstate", true), () => step("manager: told only the owner can reinstate", false));

// 5. owner reinstates
await o.locator("nav.tabs a", { hasText: "Mandate" }).first().click();
await o.getByText("Who may spend").waitFor();
await o.getByRole("button", { name: /Manage Research bot/ }).click();
await o.getByRole("button", { name: "Reinstate this grant" }).click();
await o.getByRole("button", { name: "Confirm reinstate" }).click();
await o.getByText("Grant reinstated").waitFor({ timeout: 120000 }).then(() => step("owner: reinstates the grant", true), () => step("owner: reinstates the grant", false));
await a.reload(); await a.getByRole("button", { name: /Continue as Research bot/ }).click(); await a.getByText("Who may spend").waitFor({ timeout: 120000 });
await tab(a, "Ask");
r = await ask(a, "pay 20 USD to aws for cloud");       step("agent: can ask again after reinstatement", r.stamp === "Approved", r.stamp);

// 6. history seal and invariants
await o.reload(); await o.getByRole("button", { name: /Continue as Nabil/ }).click(); await o.getByText("Who may spend").waitFor({ timeout: 120000 });
await o.getByText("History intact").waitFor({ timeout: 120000 }).then(() => step("owner: history seal is green", true), () => step("owner: history seal is green", false));
step("owner: ledger checks pass", (await o.getByText(/ledger checks pass/).count()) > 0);

// 7. owner revokes the manager; the agent below is cut off
await o.getByRole("button", { name: /Manage Ops bot/ }).click();
await o.getByRole("button", { name: /Revoke/ }).first().click();
const confirm = o.getByRole("button", { name: /Confirm revoke|Revoke this grant|Yes, revoke/ });
if (await confirm.count()) await confirm.first().click();
await o.getByText(/revoked/i).first().waitFor({ timeout: 120000 }).then(() => step("owner: revokes the manager", true), () => step("owner: revokes the manager", false));
await a.reload(); await a.getByRole("button", { name: /Continue as Research bot/ }).click();
await a.locator(".app").waitFor({ timeout: 120000 });
await a.waitForTimeout(8000);
await tab(a, "Ask");
const cut = await a.getByText(/do not hold an active grant/).count();
step("agent: cut off after the manager above is revoked", cut > 0 || (await a.locator("#ask-grant option").count()) === 0);

await b.close();
console.log(fails.length ? `FLOW FAILED: ${fails.join("; ")}` : "FLOW OK");
process.exit(fails.length ? 1 : 0);
