ALTER TABLE course_documents
    DROP COLUMN IF EXISTS source_url;

ALTER TABLE course_documents
    DROP COLUMN IF EXISTS crawl_date;

ALTER TABLE videos
    DROP COLUMN IF EXISTS transcript;

ALTER TABLE videos
    DROP COLUMN IF EXISTS transcript_url;
