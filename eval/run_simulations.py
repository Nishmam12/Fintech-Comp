"""Run every attack scenario once against the unsafe baseline and the kernel; save the measured output.

    cd backend && uv run python ../eval/run_simulations.py
Results: eval/results/<date>/simulations-<time>.json (evidence for the security self-assessment).
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from budget_kernel import simulation
from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool
from budget_kernel.db.migrate import migrate

ROOT = Path(__file__).resolve().parent
st = Settings.load()
migrate(st, st.test_schema)           # simulations use the test schema so nothing touches app data
pool = make_pool(st, st.test_schema)
runs = [simulation.run(pool, name) for name in sorted(simulation.SCENARIOS)]
pool.close()
now = datetime.now(timezone.utc)
out = ROOT / "results" / now.strftime("%Y-%m-%d")
out.mkdir(parents=True, exist_ok=True)
path = out / f"simulations-{now.strftime('%H%M%S')}.json"
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
path.write_text(json.dumps({"ran_at": now.isoformat(), "git_commit": commit, "scenarios": runs}, indent=2, default=str), encoding="utf-8")
for r in runs:
    n, k = r["naive"], r["kernel"]
    print(f"{r['scenario']:26} baseline violated={n['violated']!s:5} | kernel violated={k['violated']!s:5} | {k['summary'][:90]}")
print("saved", path)
