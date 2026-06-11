-- Collapse course_documents into the books-first attachment model.
--
-- Book-pointer rows become course_attachments rows. Direct PDF/EPUB rows
-- become ordinary library books plus attachments, and their copied chunks are
-- re-keyed from doc_type='course' to the new book ids. Chunk copies that came
-- from book-pointer rows are exact duplicates of the book's own chunks and are
-- deleted. After this migration no chunk carries doc_type='course' or a
-- course_id metadata key, and course_documents is gone.
--
-- Image rows were already removed by 037. Direct rows in formats books cannot
-- represent (txt/md/fb2/mobi/svg/xps — the books CHECK allows pdf/epub only)
-- have no destination; their rows and chunks are dropped with the table.

-- Snapshot the inputs so the final verification can assert exact deltas.
CREATE TEMP TABLE _mig055_before ON COMMIT DROP AS
SELECT
    (SELECT COUNT(*) FROM rag_document_chunks) AS total_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks WHERE doc_type = 'course') AS course_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks
      WHERE doc_type = 'course' AND metadata->>'source_book_id' IS NOT NULL) AS pointer_copy_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks WHERE doc_type = 'book') AS book_chunks,
    (SELECT COUNT(*) FROM course_documents WHERE book_id IS NOT NULL) AS pointer_rows,
    (SELECT COUNT(*) FROM course_documents
      WHERE book_id IS NULL AND document_type IN ('pdf', 'epub')) AS direct_rows;

-- 1) Book-pointer rows -> attachments.
INSERT INTO course_attachments (course_id, book_id)
SELECT cd.course_id, cd.book_id
FROM course_documents cd
WHERE cd.book_id IS NOT NULL
ON CONFLICT (course_id, book_id) DO NOTHING;

-- 2) Direct PDF/EPUB rows -> ordinary books owned by the course's user.
-- The mapping table carries the fresh book id used for chunk re-keying.
CREATE TEMP TABLE _mig055_direct_books ON COMMIT DROP AS
SELECT
    cd.id AS document_id,
    cd.course_id,
    c.user_id,
    gen_random_uuid() AS new_book_id,
    cd.title,
    cd.document_type,
    cd.file_path,
    EXISTS (
        SELECT 1 FROM rag_document_chunks ch
        WHERE ch.doc_type = 'course'
          AND ch.metadata->>'source_book_id' IS NULL
          AND ch.metadata->>'course_id' = cd.course_id::text
          AND ch.metadata->>'document_id' = cd.id::text
    ) AS has_chunks
FROM course_documents cd
JOIN courses c ON c.id = cd.course_id
WHERE cd.book_id IS NULL
  AND cd.document_type IN ('pdf', 'epub');

INSERT INTO books (id, user_id, title, author, file_path, file_type, file_size, rag_status, storage_provider)
SELECT
    d.new_book_id,
    d.user_id,
    LEFT(d.title, 500),
    'Unknown',
    LEFT(COALESCE(d.file_path, ''), 1000),
    d.document_type,
    0,
    CASE WHEN d.has_chunks THEN 'completed' ELSE 'failed' END,
    'local'
FROM _mig055_direct_books d;

INSERT INTO course_attachments (course_id, book_id)
SELECT d.course_id, d.new_book_id
FROM _mig055_direct_books d
ON CONFLICT (course_id, book_id) DO NOTHING;

-- 3) Re-key the direct rows' chunks to their new books and strip the stale
-- metadata keys in the same UPDATE: no chunk may keep a course_id key.
UPDATE rag_document_chunks ch
SET doc_type = 'book',
    doc_id = d.new_book_id,
    metadata = COALESCE(ch.metadata, '{}'::jsonb)
        - 'course_id' - 'document_id' - 'source_book_id' - 'source_doc_type'
FROM _mig055_direct_books d
WHERE ch.doc_type = 'course'
  AND ch.metadata->>'source_book_id' IS NULL
  AND ch.metadata->>'course_id' = d.course_id::text
  AND ch.metadata->>'document_id' = d.document_id::text;

-- 4) Drop the remaining doc_type='course' chunks: book-pointer copies
-- (duplicates of the book's own chunks) and unmappable leftovers.
DELETE FROM rag_document_chunks WHERE doc_type = 'course';

-- 5) Verify exact deltas before dropping anything; abort the whole
-- transaction on any mismatch.
DO $$
DECLARE
    before RECORD;
    direct_chunks BIGINT;
    after_total BIGINT;
    after_course BIGINT;
    after_book BIGINT;
    after_course_id_keys BIGINT;
    missing_pointer_attachments BIGINT;
    missing_direct_attachments BIGINT;
BEGIN
    SELECT * INTO before FROM _mig055_before;

    SELECT COUNT(*) INTO direct_chunks
    FROM rag_document_chunks ch
    JOIN _mig055_direct_books d ON ch.doc_id = d.new_book_id AND ch.doc_type = 'book';

    SELECT COUNT(*) INTO after_total FROM rag_document_chunks;
    SELECT COUNT(*) INTO after_course FROM rag_document_chunks WHERE doc_type = 'course';
    SELECT COUNT(*) INTO after_book FROM rag_document_chunks WHERE doc_type = 'book';
    SELECT COUNT(*) INTO after_course_id_keys FROM rag_document_chunks WHERE metadata ? 'course_id';

    SELECT COUNT(*) INTO missing_pointer_attachments
    FROM course_documents cd
    WHERE cd.book_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM course_attachments ca
          WHERE ca.course_id = cd.course_id AND ca.book_id = cd.book_id
      );

    SELECT COUNT(*) INTO missing_direct_attachments
    FROM _mig055_direct_books d
    WHERE NOT EXISTS (
        SELECT 1 FROM course_attachments ca
        WHERE ca.course_id = d.course_id AND ca.book_id = d.new_book_id
    );

    IF after_course <> 0 THEN
        RAISE EXCEPTION 'migration 055: % doc_type=course chunks remain', after_course;
    END IF;
    IF after_course_id_keys <> 0 THEN
        RAISE EXCEPTION 'migration 055: % chunks still carry a course_id metadata key', after_course_id_keys;
    END IF;
    IF missing_pointer_attachments <> 0 THEN
        RAISE EXCEPTION 'migration 055: % book-pointer rows missing attachments', missing_pointer_attachments;
    END IF;
    IF missing_direct_attachments <> 0 THEN
        RAISE EXCEPTION 'migration 055: % direct rows missing attachments', missing_direct_attachments;
    END IF;
    IF after_book <> before.book_chunks + direct_chunks THEN
        RAISE EXCEPTION 'migration 055: book chunks % do not equal prior % plus re-keyed %',
            after_book, before.book_chunks, direct_chunks;
    END IF;
    IF after_total <> before.total_chunks - (before.course_chunks - direct_chunks) THEN
        RAISE EXCEPTION 'migration 055: total chunks % do not match expected % (before %, course %, re-keyed %)',
            after_total, before.total_chunks - (before.course_chunks - direct_chunks),
            before.total_chunks, before.course_chunks, direct_chunks;
    END IF;

    RAISE NOTICE 'migration 055: pointer_rows=% direct_rows=% re-keyed_chunks=% deleted_chunks=%',
        before.pointer_rows, before.direct_rows, direct_chunks, before.course_chunks - direct_chunks;
END $$;

-- 6) Retire the table and its dead chunk index.
DROP TABLE course_documents;
DROP INDEX IF EXISTS rag_document_chunks_metadata_course_id_idx;
