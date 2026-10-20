// The film uses the same screenshots as the submission documents. Copy them in before studio or render instead of keeping two copies in git.
import { cpSync, mkdirSync } from "node:fs";
mkdirSync("public/screens", { recursive: true });
cpSync("../docs/submission/screenshots/r3", "public/screens", { recursive: true });
console.log("copied screenshots into public/screens");
