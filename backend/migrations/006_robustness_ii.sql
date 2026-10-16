-- 006_robustness_ii.sql (ADR-0009): hash-chained history, grant suspension, key lifecycle, per-agent budget buckets.
-- Runs inside the schema chosen by the migration runner (search_path already set). Safe on a populated schema:
-- existing audit and movement rows are chained by a backfill before the new columns become NOT NULL.

-- ---------------------------------------------------------------------------------------------- A. hash chain

CREATE TABLE chain_heads (
  chain_key   text PRIMARY KEY,                       -- 'mandate:<uuid>' or 'global'
  seq         bigint NOT NULL CHECK (seq >= 0),
  head_hash   text NOT NULL CHECK (head_hash ~ '^[0-9a-f]{64}$'),
  updated_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE chain_heads ENABLE ROW LEVEL SECURITY;

ALTER TABLE audit_events     ADD COLUMN chain_key text, ADD COLUMN seq bigint, ADD COLUMN prev_hash text, ADD COLUMN row_hash text;
ALTER TABLE ledger_movements ADD COLUMN chain_key text, ADD COLUMN seq bigint, ADD COLUMN prev_hash text, ADD COLUMN row_hash text;

-- Field encoding: NULL -> '', then length-prefixed so that no field can bleed into its neighbour.
CREATE FUNCTION bk_f(v text) RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT char_length(coalesce(v, '')) || ':' || coalesce(v, '') $$;

-- timestamptz -> integer microseconds since the Unix epoch (UTC), as text.
CREATE FUNCTION bk_us(t timestamptz) RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT (extract(epoch FROM t) * 1000000)::numeric(40,0)::bigint::text $$;

-- Canonical row string (ADR-0009 section A3). The Python verifier rebuilds this from raw column values.
CREATE FUNCTION bk_canon(tbl text, r record) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
  IF tbl = 'audit_events' THEN
    RETURN 'A|' || bk_f(r.id::text) || '|' || bk_f(r.chain_key) || '|' || bk_f(r.seq::text) || '|'
        || bk_f(r.mandate_id::text) || '|' || bk_f(r.kind) || '|' || bk_f(r.actor_principal_id::text) || '|'
        || bk_f(r.subject_id::text) || '|' || bk_f(bk_us(r.created_at)) || '|' || bk_f(r.detail::text);
  ELSIF tbl = 'ledger_movements' THEN
    RETURN 'M|' || bk_f(r.id::text) || '|' || bk_f(r.chain_key) || '|' || bk_f(r.seq::text) || '|'
        || bk_f(r.mandate_id::text) || '|' || bk_f(r.kind) || '|' || bk_f(r.amount::text) || '|'
        || bk_f(r.from_grant_id::text) || '|' || bk_f(r.from_bucket) || '|' || bk_f(r.to_grant_id::text) || '|'
        || bk_f(r.to_bucket) || '|' || bk_f(r.transaction_id::text) || '|' || bk_f(r.actor_principal_id::text) || '|'
        || bk_f(bk_us(r.created_at));
  END IF;
  RAISE EXCEPTION 'bk_canon: table % is not chained', tbl;
END $$;

CREATE FUNCTION bk_hash(prev text, canon text) RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT encode(sha256(convert_to('BK1|' || prev || '|' || canon, 'UTF8')), 'hex') $$;

-- Backfill: chain the rows that exist today, per chain, ordered by (created_at, table, id); audit before
-- ledger on a tie. The append-only triggers are lifted for the duration of this one migration only.
ALTER TABLE audit_events     DISABLE TRIGGER audit_events_append_only;
ALTER TABLE ledger_movements DISABLE TRIGGER ledger_movements_append_only;
DO $$
DECLARE
  x record; r record; h text;
  cur_key text := NULL; cur_seq bigint := 0; cur_hash text := repeat('0', 64);
BEGIN
  FOR x IN
    SELECT t, id, ck FROM (
      SELECT 'audit_events' AS t, 0 AS ord, id, created_at,
             CASE WHEN mandate_id IS NULL THEN 'global' ELSE 'mandate:' || mandate_id END AS ck FROM audit_events
      UNION ALL
      SELECT 'ledger_movements', 1, id, created_at, 'mandate:' || mandate_id FROM ledger_movements
    ) u ORDER BY ck, created_at, ord, id
  LOOP
    IF cur_key IS DISTINCT FROM x.ck THEN
      IF cur_key IS NOT NULL THEN
        INSERT INTO chain_heads(chain_key, seq, head_hash) VALUES (cur_key, cur_seq, cur_hash);
      END IF;
      cur_key := x.ck; cur_seq := 0; cur_hash := repeat('0', 64);
    END IF;
    cur_seq := cur_seq + 1;
    EXECUTE format('UPDATE %I SET chain_key = $1, seq = $2, prev_hash = $3 WHERE id = $4 RETURNING *', x.t)
      INTO r USING x.ck, cur_seq, cur_hash, x.id;
    h := bk_hash(cur_hash, bk_canon(x.t, r));
    EXECUTE format('UPDATE %I SET row_hash = $1 WHERE id = $2', x.t) USING h, x.id;
    cur_hash := h;
  END LOOP;
  IF cur_key IS NOT NULL THEN
    INSERT INTO chain_heads(chain_key, seq, head_hash) VALUES (cur_key, cur_seq, cur_hash);
  END IF;
END $$;
ALTER TABLE audit_events     ENABLE TRIGGER audit_events_append_only;
ALTER TABLE ledger_movements ENABLE TRIGGER ledger_movements_append_only;

ALTER TABLE audit_events
  ALTER COLUMN chain_key SET NOT NULL, ALTER COLUMN seq SET NOT NULL,
  ALTER COLUMN prev_hash SET NOT NULL, ALTER COLUMN row_hash SET NOT NULL,
  ADD CONSTRAINT audit_events_chain_pos UNIQUE (chain_key, seq),
  ADD CONSTRAINT audit_events_hash_shape CHECK (prev_hash ~ '^[0-9a-f]{64}$' AND row_hash ~ '^[0-9a-f]{64}$');
ALTER TABLE ledger_movements
  ALTER COLUMN chain_key SET NOT NULL, ALTER COLUMN seq SET NOT NULL,
  ALTER COLUMN prev_hash SET NOT NULL, ALTER COLUMN row_hash SET NOT NULL,
  ADD CONSTRAINT ledger_movements_chain_pos UNIQUE (chain_key, seq),
  ADD CONSTRAINT ledger_movements_hash_shape CHECK (prev_hash ~ '^[0-9a-f]{64}$' AND row_hash ~ '^[0-9a-f]{64}$');

-- Every writer goes through this trigger: values supplied by the application are overwritten. The head row
-- lock serializes writers per chain until commit; a rollback undoes the head update, so there are no gaps.
-- Lock order is always mandate row (kernel_tx) -> chain head, so no deadlock cycle exists.
CREATE FUNCTION chain_append() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text; h record;
BEGIN
  k := CASE WHEN NEW.mandate_id IS NULL THEN 'global' ELSE 'mandate:' || NEW.mandate_id END;
  INSERT INTO chain_heads(chain_key, seq, head_hash, updated_at) VALUES (k, 1, repeat('0', 64), clock_timestamp())
  ON CONFLICT (chain_key) DO UPDATE SET seq = chain_heads.seq + 1, updated_at = clock_timestamp()
  RETURNING seq, head_hash INTO h;     -- head_hash is still the previous head: it is updated below
  NEW.chain_key := k;
  NEW.seq := h.seq;
  NEW.prev_hash := h.head_hash;
  NEW.row_hash := bk_hash(NEW.prev_hash, bk_canon(TG_TABLE_NAME, NEW));
  UPDATE chain_heads SET head_hash = NEW.row_hash WHERE chain_key = k;
  RETURN NEW;
END $$;
CREATE TRIGGER audit_events_chain BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION chain_append();
CREATE TRIGGER ledger_movements_chain BEFORE INSERT ON ledger_movements
  FOR EACH ROW EXECUTE FUNCTION chain_append();

-- ---------------------------------------------------------------------------------------- B. circuit breaker

ALTER TABLE grants
  ADD COLUMN suspended_at   timestamptz,
  ADD COLUMN suspend_reason text CHECK (suspend_reason IN ('STRIKES', 'MANUAL')),
  ADD COLUMN reinstated_at  timestamptz;
ALTER TABLE grants DROP CONSTRAINT grants_status_check;
ALTER TABLE grants ADD CONSTRAINT grants_status_check
  CHECK (status IN ('active', 'suspended', 'revoked', 'expired'));
ALTER TABLE grants ADD CONSTRAINT grants_suspension_consistent
  CHECK ((status = 'suspended') = (suspended_at IS NOT NULL) AND (suspended_at IS NULL) = (suspend_reason IS NULL));

CREATE TABLE grant_strikes (
  id                  bigserial PRIMARY KEY,
  mandate_id          uuid NOT NULL REFERENCES mandates(id),
  grant_id            uuid NOT NULL REFERENCES grants(id),
  actor_principal_id  uuid NOT NULL REFERENCES principals(id),
  kind                text NOT NULL CHECK (kind IN ('REFUSAL', 'INJECTION')),
  reason              text NOT NULL,
  weight              smallint NOT NULL CHECK (weight > 0),
  created_at          timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX grant_strikes_grant_idx ON grant_strikes (grant_id, created_at);
CREATE TRIGGER grant_strikes_append_only BEFORE UPDATE OR DELETE ON grant_strikes
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE grant_strikes ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------------ C. key lifecycle (BK-412)

ALTER TABLE principals
  ADD COLUMN key_expires_at timestamptz,
  ADD COLUMN disabled_at    timestamptz,
  ADD COLUMN key_rotated_at timestamptz;

-- ------------------------------------------------------------------------- D. per-agent inference budget (BK-304)

ALTER TABLE budget_buckets DROP CONSTRAINT budget_buckets_bucket_check;
ALTER TABLE budget_buckets ADD CONSTRAINT budget_buckets_bucket_check
  CHECK (bucket IN ('global', 'primary', 'escalation', 'retries', 'eval') OR bucket ~ '^principal:[0-9a-f-]{36}$');
