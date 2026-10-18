// BK-514: fail when a refusal / review / permission code the backend can emit has no plain-language text in
// lib/api.ts REASON_TEXT. Run from frontend/: `npm run check:reasons`.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const backend = join(here, "..", "..", "backend", "src", "budget_kernel");

// Quoted ALL_CAPS strings in the backend that are not reasons shown to a person:
//  - env var and config names, HTTP methods;
//  - audit event kinds (TX_*, GRANT_DELEGATED ...), which the Activity screen words through lib/describe.ts;
//  - codes whose own server message is shown instead (input validation) or that are integrity-chain internals
//    shown through the History badge.
const NOT_A_REASON = new Set([
  "DELETE", "OPTIONS", "BASE_SEPOLIA_RPC_URL", "SETTLEMENT_PRIVATE_KEY", "BK_WORKER",
  "GRANT_DELEGATED", "GRANT_REINSTATED", "MANDATE_CREATED", "KEY_ROTATED", "SETTLER_BOUND", "SETTLER_UNBOUND",
  "REFUSAL", "REFUSED", "STRIKES", "MANUAL", "INJECTION",
  "BAD_AMOUNT", "BAD_CURRENCY", "BAD_DATETIME", "BAD_EXPIRY", "BAD_IDEMPOTENCY_KEY", "BAD_RESERVE", "BAD_SCOPE",
  "BAD_SIGNAL", "VALIDATION_FAILED", "DELEGATION_REJECTED", "CONFLICT", "FORBIDDEN", "NOT_FOUND", "KERNEL_ERROR",
  "KERNEL_INVARIANT", "HASH_MISMATCH", "HEAD_MISMATCH", "PREV_MISMATCH", "SEQ_GAP", "ANCHOR_MISMATCH",
]);
const ignored = (c) => NOT_A_REASON.has(c) || c.startsWith("BK_") || c.startsWith("TX_");

const files = ["kernel", "api"].flatMap((d) =>
  readdirSync(join(backend, d)).filter((f) => f.endsWith(".py")).map((f) => join(backend, d, f)));
const found = new Set();
// The handover's own net: every quoted ALL_CAPS string of 6+ characters (plus code="..." for shorter ones).
const patterns = [/["']([A-Z][A-Z_]{5,})["']/g, /code\s*=\s*["']([A-Z_]+)["']/g];
for (const f of files) {
  const src = readFileSync(f, "utf8");
  for (const re of patterns) for (const m of src.matchAll(re)) if (!ignored(m[1])) found.add(m[1]);
}

const api = readFileSync(join(here, "..", "lib", "api.ts"), "utf8");
const block = api.slice(api.indexOf("const REASON_TEXT"), api.indexOf("export const reasonText"));
const mapped = new Set([...block.matchAll(/^\s+([A-Z][A-Z_]+):/gm)].map((m) => m[1]));

const missing = [...found].filter((c) => !mapped.has(c)).sort();
if (missing.length) {
  console.error(`REASON_TEXT is missing ${missing.length} code(s): ${missing.join(", ")}`);
  process.exit(1);
}
console.log(`ok: ${found.size} backend codes checked, ${mapped.size} have plain text`);
