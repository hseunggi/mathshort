ALTER TABLE users
    ADD COLUMN verified BOOLEAN NOT NULL DEFAULT FALSE AFTER email,
    ADD COLUMN verification_code VARCHAR(6) NULL AFTER verified,
    ADD COLUMN expires_at DATETIME(6) NULL AFTER verification_code;

ALTER TABLE users
    ADD CONSTRAINT uk_users_email UNIQUE (email);
