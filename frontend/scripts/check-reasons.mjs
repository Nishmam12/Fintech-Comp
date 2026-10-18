// BK-514: fail when a refusal / review / permission code the backend can emit has no plain-language text in
// lib/api.ts REASON_TEXT. Run from frontend/: `npm run check:reasons`.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const backend = join(here, "..", "..", "backend", "src", "budget_kernel");

// Codes that never reach a screen as a reason: the server's own message is shown instead, or they are internal
// (input validation, integrity-chain internals, circuit-breaker labels shown through their own UI).
const SERVER_MESSAGE = new Set([
  "BAD_AMOUNT", "BAD_CURRENCY", "BAD_DATETIME", "BAD_EXPIRY", "BAD_IDEMPOTENCY_KEY", "BAD_RESERVE", "BAD_SCOPE",
  "BAD_SIGNAL", "VALIDATION_FAILED", "DELEGATION_REJECTED", "CONFLICT", "FORBIDDEN", "NOT_FOUND", "KERNEL_ERROR",
  "KERNEL_INVARIANT", "HASH_MISMATCH", "HEAD_MISMATCH", "PREV_MISMATCH", "SEQ_GAP", "INJECTION", "STRIKES", "MANUAL",
]);

const files = ["kernel", "api"].flatMap((d) =>
  readdirSync(join(backend, d)).filter((f) => f.endsWith(".py")).map((f) => join(backend, d, f)));
const found = new Set();
const patterns = [
  /(?:return|reason\s*=|held\s*=|code\s*=)\s*\(?["']([A-Z][A-Z_]{4,})["']/g,
  /reject_reason\s*=\s*'([A-Z_]+)'/g,
];
for (const f of files) {
  const src = readFileSync(f, "utf8");
  for (const re of patterns) for (const m of src.matchAll(re)) found.add(m[1]);
}

const api = readFileSync(join(here, "..", "lib", "api.ts"), "utf8");
const block = api.slice(api.indexOf("const REASON_TEXT"), api.indexOf("export const reasonText"));
const mapped = new Set([...block.matchAll(/^\s+([A-Z][A-Z_]+):/gm)].map((m) => m[1]));

const missing = [...found].filter((c) => !mapped.has(c) && !SERVER_MESSAGE.has(c)).sort();
if (missing.length) {
  console.error(`REASON_TEXT is missing ${missing.length} code(s): ${missing.join(", ")}`);
  process.exit(1);
}
console.log(`ok: ${found.size} backend codes checked, ${mapped.size} have plain text`);
