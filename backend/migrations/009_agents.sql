-- 009_agents.sql: which human created which agent principal (docs/plans/LOGIN_PLAN.md, setup flow).
-- Used to cap agent creation per person and to list "my agents" for delegation. It grants no authority by itself:
-- an agent can spend only what a grant gives it.

ALTER TABLE principals ADD COLUMN created_by uuid REFERENCES principals(id);
CREATE INDEX principals_created_by_idx ON principals (created_by) WHERE created_by IS NOT NULL;
