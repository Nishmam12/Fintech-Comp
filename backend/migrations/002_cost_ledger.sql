-- 002_cost_ledger.sql: inference cost ledger (ADR-0006). Separate from the mandate money ledger;
-- never touched inside a kernel (mandate-lock) transaction.

CREATE TABLE budget_buckets (
  month           date NOT NULL CHECK (month = date_trunc('month', month)::date),
  bucket          text NOT NULL CHECK (bucket IN ('global', 'primary', 'escalation', 'retries', 'eval')),
  cap_micro_usd   bigint NOT NULL CHECK (cap_micro_usd >= 0),
  reserved_micro  bigint NOT NULL DEFAULT 0 CHECK (reserved_micro >= 0),
  spent_micro     bigint NOT NULL DEFAULT 0 CHECK (spent_micro >= 0),
  -- deliberately no CHECK (reserved + spent <= cap): a provider overrun must still be recordable.
  -- The cap is enforced at reservation time only.
  PRIMARY KEY (month, bucket)
);

CREATE TABLE inference_calls (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  month                date NOT NULL,
  route_bucket         text NOT NULL CHECK (route_bucket IN ('primary', 'escalation', 'retries', 'eval')),
  provider             text NOT NULL,
  model_id             text NOT NULL,
  rate_card_version    text NOT NULL,
  -- prices frozen at reservation so reconciliation never depends on a later rate-card edit
  price_in_micro_per_mtok      bigint NOT NULL,
  price_cached_micro_per_mtok  bigint NOT NULL,
  price_out_micro_per_mtok     bigint NOT NULL,
  reasoning_billing    text NOT NULL CHECK (reasoning_billing IN ('as_output', 'separate', 'none')),
  fixed_fee_micro      bigint NOT NULL DEFAULT 0,
  est_micro            bigint NOT NULL CHECK (est_micro > 0),
  actual_micro         bigint,
  overrun_micro        bigint NOT NULL DEFAULT 0 CHECK (overrun_micro >= 0),
  status               text NOT NULL CHECK (status IN
                         ('reserved', 'dispatched', 'reconciled', 'released', 'charged_worst_case')),
  input_tokens         integer,
  output_tokens        integer,
  reasoning_tokens     integer,
  cached_tokens        integer,
  purpose              text,                       -- e.g. 'interpret', 'repair', 'eval' (no prompt text stored)
  created_at           timestamptz NOT NULL DEFAULT now(),
  dispatched_at        timestamptz,
  reconciled_at        timestamptz,
  FOREIGN KEY (month, route_bucket) REFERENCES budget_buckets(month, bucket)
);
CREATE INDEX inference_calls_open_idx ON inference_calls (created_at) WHERE status IN ('reserved', 'dispatched');
CREATE INDEX inference_calls_month_idx ON inference_calls (month, route_bucket);

ALTER TABLE budget_buckets  ENABLE ROW LEVEL SECURITY;
ALTER TABLE inference_calls ENABLE ROW LEVEL SECURITY;
