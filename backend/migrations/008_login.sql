-- 008_login.sql: username and password login, and sessions (docs/plans/LOGIN_PLAN.md).
-- A login produces a session token that resolves to the same principal as an API key; nothing in the kernel changes.
-- Passwords exist for humans only (a CHECK says so); agents and services keep API keys.

ALTER TABLE principals
  ADD COLUMN username            text,
  ADD COLUMN password_hash       text,
  ADD COLUMN password_changed_at timestamptz,
  ADD COLUMN failed_logins       integer NOT NULL DEFAULT 0,
  ADD COLUMN locked_until        timestamptz,
  ADD CONSTRAINT principals_username_format CHECK (username IS NULL OR username ~ '^[a-z0-9][a-z0-9._-]{2,31}$'),
  ADD CONSTRAINT principals_password_needs_username CHECK (password_hash IS NULL OR username IS NOT NULL),
  ADD CONSTRAINT principals_password_humans_only CHECK (password_hash IS NULL OR kind = 'human');

CREATE UNIQUE INDEX principals_username_key ON principals (username);

-- Only the SHA-256 of a session token is stored; the raw token is returned once at login.
CREATE TABLE sessions (
  token_hash   text PRIMARY KEY,
  principal_id uuid NOT NULL REFERENCES principals(id),
  created_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz
);
CREATE INDEX sessions_principal_idx ON sessions (principal_id);
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
