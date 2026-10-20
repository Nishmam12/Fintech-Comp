"""Empty the scratch schema bk_dev so the demo reseeds to exactly one mandate. Refuses any other schema."""
from budget_kernel.config import Settings
from budget_kernel.db.connection import make_pool

p = make_pool(Settings.load(), "bk_dev", max_size=1)
with p.connection() as c:
    c.execute("TRUNCATE principals, mandates, grants, transactions, ledger_movements, audit_events,"
              " budget_buckets, inference_calls, chain_heads, grant_strikes, sessions CASCADE")
p.close()
print("bk_dev emptied")
