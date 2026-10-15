-- 004_naive_baseline.sql: tables for the INTENTIONALLY UNSAFE baseline used only by the attack demo.
-- These are deliberately written the way unprotected code usually is: no CHECK (available >= 0), no
-- uniqueness on idempotency keys, no locking. The secure path never reads or writes them (a boundary
-- test enforces that nothing outside simulation/ imports the baseline module).

CREATE TABLE naive_wallets (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id      uuid NOT NULL,
  parent_id   uuid,
  available   bigint NOT NULL,        -- no CHECK: overspend is allowed to happen, so it can be measured
  status      text NOT NULL DEFAULT 'active',
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX naive_wallets_run_idx ON naive_wallets (run_id);

CREATE TABLE naive_spends (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id      uuid NOT NULL,
  wallet_id   uuid NOT NULL,
  amount      bigint NOT NULL,
  idem_key    text,                   -- recorded but never enforced
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX naive_spends_run_idx ON naive_spends (run_id);

ALTER TABLE naive_wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE naive_spends  ENABLE ROW LEVEL SECURITY;
