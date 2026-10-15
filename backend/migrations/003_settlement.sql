-- 003_settlement.sql: testnet settlement adapter (ADR-0007). Not part of the kernel's authority:
-- these tables record what was signed and sent for a kernel-reserved transaction.

CREATE TABLE settlement_accounts (
  chain_id    int  NOT NULL,
  address     text NOT NULL,
  next_nonce  bigint NOT NULL CHECK (next_nonce >= 0),
  PRIMARY KEY (chain_id, address)
);

CREATE TABLE chain_settlements (
  transaction_id     uuid PRIMARY KEY REFERENCES transactions(id),   -- at most one transfer per kernel tx
  chain_id           int  NOT NULL,
  from_address       text NOT NULL,
  nonce              bigint NOT NULL,
  to_address         text NOT NULL,
  token_address      text NOT NULL,
  token_amount       numeric(78,0) NOT NULL CHECK (token_amount > 0),
  raw_tx             bytea NOT NULL,
  tx_hash            text NOT NULL UNIQUE,
  status             text NOT NULL CHECK (status IN ('signed', 'broadcast', 'confirmed', 'failed', 'stuck')),
  broadcast_attempts int  NOT NULL DEFAULT 0,
  last_error         text,                       -- sanitized; never key material
  block_number       bigint,
  confirmed_at       timestamptz,
  nonce_gone_since   timestamptz,                -- first time the nonce was seen consumed with no receipt for our hash
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chain_id, from_address, nonce)
);
CREATE INDEX chain_settlements_pending_idx ON chain_settlements (status)
  WHERE status IN ('signed', 'broadcast', 'stuck');

ALTER TABLE settlement_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chain_settlements   ENABLE ROW LEVEL SECURITY;
