ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS video_status VARCHAR(20) NOT NULL DEFAULT 'NONE' AFTER output_mp4_path,
    ADD COLUMN IF NOT EXISTS video_error_message LONGTEXT NULL AFTER video_status;

UPDATE jobs
SET video_status = 'NONE'
WHERE video_status IS NULL OR video_status = '';
