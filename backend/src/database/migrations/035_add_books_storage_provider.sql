ALTER TABLE books ADD COLUMN storage_provider VARCHAR(20);

UPDATE books
SET storage_provider = 'r2'
WHERE storage_provider IS NULL;

ALTER TABLE books ALTER COLUMN storage_provider SET DEFAULT 'local';

ALTER TABLE books ALTER COLUMN storage_provider SET NOT NULL;

ALTER TABLE books
ADD CONSTRAINT books_storage_provider_check CHECK (storage_provider IN ('local', 'r2', 'gcs'));
