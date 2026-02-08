ALTER TABLE users
    ADD COLUMN provider VARCHAR(20) NOT NULL DEFAULT 'LOCAL' AFTER username,
    ADD COLUMN provider_id VARCHAR(200) NULL AFTER provider,
    ADD COLUMN email VARCHAR(255) NULL AFTER provider_id,
    ADD COLUMN name VARCHAR(100) NULL AFTER email;

UPDATE users
SET name = username
WHERE name IS NULL OR name = '';

ALTER TABLE users
    ADD CONSTRAINT uk_users_provider_provider_id UNIQUE (provider, provider_id);
