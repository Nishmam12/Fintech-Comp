-- 007_anchors.sql (ADR-0009 A5, BK-401): on-chain anchors of the hash-chain heads. Evidence only: nothing here
-- authorizes anything, and the kernel never reads chain state.

CREATE TABLE anchors (
  id                 bigserial PRIMARY KEY,
  chain_id           int    NOT NULL,
  from_address       text   NOT NULL,
  nonce              bigint NOT NULL,
  digest             text   NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  raw_tx             bytea  NOT NULL,
  tx_hash            text   NOT NULL UNIQUE,
  status             text   NOT NULL CHECK (status IN ('signed', 'broadcast', 'confirmed', 'failed', 'stuck')),
  broadcast_attempts int    NOT NULL DEFAULT 0,
  last_error         text,                       -- sanitized; never key material
  block_number       bigint,
  nonce_gone_since   timestamptz,                -- same meaning as in chain_settlements
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chain_id, from_address, nonce)
);
CREATE INDEX anchors_pending_idx ON anchors (status) WHERE status IN ('signed', 'broadcast', 'stuck');

CREATE TABLE anchor_heads (
  anchor_id  bigint NOT NULL REFERENCES anchors(id),
  chain_key  text   NOT NULL,
  seq        bigint NOT NULL,
  head_hash  text   NOT NULL,
  PRIMARY KEY (anchor_id, chain_key)
);

ALTER TABLE anchors      ENABLE ROW LEVEL SECURITY;
ALTER TABLE anchor_heads ENABLE ROW LEVEL SECURITY;

-- A payment and an anchor must never share a nonce. Both draw from settlement_accounts (whose row lock already
-- serializes them); this trigger makes the property hold even if some future writer bypasses the allocator.
CREATE FUNCTION nonce_disjoint() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE other text := CASE TG_TABLE_NAME WHEN 'anchors' THEN 'chain_settlements' ELSE 'anchors' END;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.chain_id || ':' || NEW.from_address || ':' || NEW.nonce, 0));
  IF EXISTS (SELECT 1 FROM chain_settlements WHERE TG_TABLE_NAME = 'anchors' AND chain_id = NEW.chain_id
               AND from_address = NEW.from_address AND nonce = NEW.nonce)
     OR EXISTS (SELECT 1 FROM anchors WHERE TG_TABLE_NAME = 'chain_settlements' AND chain_id = NEW.chain_id
               AND from_address = NEW.from_address AND nonce = NEW.nonce) THEN
    RAISE EXCEPTION 'nonce % already used by %', NEW.nonce, other USING ERRCODE = 'unique_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER anchors_nonce_disjoint BEFORE INSERT ON anchors
  FOR EACH ROW EXECUTE FUNCTION nonce_disjoint();
CREATE TRIGGER chain_settlements_nonce_disjoint BEFORE INSERT ON chain_settlements
  FOR EACH ROW EXECUTE FUNCTION nonce_disjoint();
