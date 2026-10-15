-- 005_robustness.sql (ADR-0008): velocity windows and the approval threshold.
--   reserved_at   when funds were actually held (set on entering 'reserved'); the velocity window is measured on it,
--                 so a proposal approved hours later counts from approval, not from the request.
--   review_reason why a transaction was held as 'proposed'.

ALTER TABLE transactions
  ADD COLUMN reserved_at   timestamptz,
  ADD COLUMN review_reason text CHECK (review_reason IN ('CALLER_FLAGGED', 'ABOVE_THRESHOLD'));

UPDATE transactions SET reserved_at = created_at WHERE state IN ('reserved', 'submitted', 'settled');

-- Anything holding or having spent funds must carry the time it was reserved. 'released' rows keep their value.
ALTER TABLE transactions
  ADD CONSTRAINT transactions_reserved_at_set
  CHECK (state NOT IN ('reserved', 'submitted', 'settled') OR reserved_at IS NOT NULL);

CREATE INDEX transactions_mandate_reserved_idx ON transactions (mandate_id, reserved_at);
