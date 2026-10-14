-- 001_core.sql: principals, mandates, grants, transactions, ledger movements, audit.
-- Implements ADR-0004 (move-based accounting) and ADR-0005 (lifecycle / idempotency).
-- Runs inside the schema chosen by the migration runner (search_path already set).
-- All money is BIGINT minor units. There is deliberately no derived "remaining" column.

CREATE TABLE principals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  kind          text NOT NULL CHECK (kind IN ('human', 'agent', 'service')),
  api_key_hash  text UNIQUE,                       -- sha256 hex of the key; raw keys are never stored
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE mandates (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_principal_id  uuid NOT NULL REFERENCES principals(id),
  currency            char(3) NOT NULL,
  total               bigint NOT NULL CHECK (total > 0),
  protected_reserve   bigint NOT NULL CHECK (protected_reserve >= 0 AND protected_reserve <= total),
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen')),
  expires_at          timestamptz NOT NULL,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grants (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id          uuid NOT NULL REFERENCES mandates(id),
  parent_id           uuid REFERENCES grants(id),
  path                uuid[] NOT NULL,             -- ancestors root..self, includes self
  depth               smallint NOT NULL CHECK (depth BETWEEN 0 AND 4),
  holder_principal_id uuid NOT NULL REFERENCES principals(id),
  available           bigint NOT NULL CHECK (available >= 0),
  reserved            bigint NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  settled             bigint NOT NULL DEFAULT 0 CHECK (settled >= 0),
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
  expires_at          timestamptz NOT NULL,
  scope               jsonb NOT NULL,              -- immutable after insert (enforced by trigger below)
  idempotency_key     text,
  payload_hash        text,                        -- delegation replay detection
  created_at          timestamptz NOT NULL DEFAULT now(),
  revoked_at          timestamptz,
  CHECK (cardinality(path) = depth + 1),
  CHECK (path[cardinality(path)] = id),
  CHECK ((parent_id IS NULL) = (depth = 0))
);
CREATE UNIQUE INDEX grants_one_root_per_mandate ON grants (mandate_id) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX grants_delegation_idem ON grants (parent_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX grants_mandate_idx ON grants (mandate_id);
CREATE INDEX grants_path_gin ON grants USING gin (path);
CREATE INDEX grants_parent_idx ON grants (parent_id);

CREATE TABLE transactions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id          uuid NOT NULL REFERENCES mandates(id),
  grant_id            uuid NOT NULL REFERENCES grants(id),
  amount              bigint NOT NULL CHECK (amount > 0),
  currency            char(3) NOT NULL,
  recipient           text NOT NULL,
  category            text NOT NULL,
  state               text NOT NULL CHECK (state IN
                        ('proposed', 'rejected', 'reserved', 'submitted', 'settled', 'released')),
  reject_reason       text,
  idempotency_key     text NOT NULL,
  payload_hash        text NOT NULL,
  reserve_expires_at  timestamptz,
  proposal            jsonb,                       -- sanitized UNTRUSTED model proposal, display/audit only
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (grant_id, idempotency_key),
  CHECK ((state = 'rejected') = (reject_reason IS NOT NULL))
);
CREATE INDEX transactions_grant_state_idx ON transactions (grant_id, state);
CREATE INDEX transactions_mandate_state_idx ON transactions (mandate_id, state);

CREATE TABLE ledger_movements (
  id                  bigserial PRIMARY KEY,
  mandate_id          uuid NOT NULL REFERENCES mandates(id),
  kind                text NOT NULL,
  amount              bigint NOT NULL CHECK (amount > 0),
  from_grant_id       uuid REFERENCES grants(id),
  from_bucket         text,
  to_grant_id         uuid REFERENCES grants(id),
  to_bucket           text,
  transaction_id      uuid REFERENCES transactions(id),
  actor_principal_id  uuid REFERENCES principals(id),
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ledger_movements_mandate_idx ON ledger_movements (mandate_id, id);

CREATE TABLE audit_events (
  id                  bigserial PRIMARY KEY,
  mandate_id          uuid REFERENCES mandates(id),
  kind                text NOT NULL,
  actor_principal_id  uuid,
  subject_id          uuid,
  detail              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_mandate_idx ON audit_events (mandate_id, id);

-- Append-only: audit and movement history cannot be edited or deleted by the application role.
CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% on % is not allowed (append-only)', TG_OP, TG_TABLE_NAME;
END $$;
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER ledger_movements_append_only BEFORE UPDATE OR DELETE ON ledger_movements
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- A grant's scope, holder, parent, path and expiry never change after creation (ADR-0004).
CREATE FUNCTION grants_immutable_fields() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.scope IS DISTINCT FROM OLD.scope
     OR NEW.parent_id IS DISTINCT FROM OLD.parent_id
     OR NEW.path IS DISTINCT FROM OLD.path
     OR NEW.mandate_id IS DISTINCT FROM OLD.mandate_id
     OR NEW.holder_principal_id IS DISTINCT FROM OLD.holder_principal_id
     OR NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
    RAISE EXCEPTION 'grant % has immutable fields (scope/parent/path/holder/expiry)', OLD.id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER grants_immutable BEFORE UPDATE ON grants
  FOR EACH ROW EXECUTE FUNCTION grants_immutable_fields();

-- The Supabase Data API must never reach these tables: RLS on, no policies.
-- The backend connects as the table owner through the pooler, which bypasses RLS.
ALTER TABLE principals       ENABLE ROW LEVEL SECURITY;
ALTER TABLE mandates         ENABLE ROW LEVEL SECURITY;
ALTER TABLE grants           ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events     ENABLE ROW LEVEL SECURITY;
