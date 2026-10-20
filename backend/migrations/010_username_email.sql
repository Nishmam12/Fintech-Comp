-- 010_username_email.sql: a username may be an email address (letters, digits, . _ - @ +, up to 64 characters).
ALTER TABLE principals DROP CONSTRAINT principals_username_format;
ALTER TABLE principals ADD CONSTRAINT principals_username_format
  CHECK (username IS NULL OR username ~ '^[a-z0-9][a-z0-9._@+-]{2,63}$');
