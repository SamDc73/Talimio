-- Collapse course_documents into the books-first attachment model.
--
-- Book-pointer rows become course_attachments rows. Their copied chunks are
-- exact duplicates of the book's own chunks and are deleted. Direct legacy
-- rows cannot honestly become books because course_documents never stored
-- book-required metadata, and the production count is small enough to clean up
-- once instead of carrying a second course-source path forever.
--
-- After this migration no chunk carries doc_type='course' or a course_id
-- metadata key, and course_documents is gone.

-- Preflight before mutating anything. The migration is allowed to delete direct
-- legacy course chunks and verified book-pointer chunk copies; book-pointer
-- chunks must prove they duplicate their source book chunks before deletion.
DO $$
DECLARE
    pointer_chunks_without_attachment_source BIGINT;
    pointer_chunks_without_matching_book_chunk BIGINT;
BEGIN
    SELECT COUNT(*) INTO pointer_chunks_without_attachment_source
    FROM rag_document_chunks ch
    WHERE ch.doc_type = 'course'
      AND ch.metadata->>'source_book_id' IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM course_documents cd
          WHERE cd.book_id IS NOT NULL
            AND ch.metadata->>'course_id' = cd.course_id::text
            AND ch.metadata->>'source_book_id' = cd.book_id::text
      );

    SELECT COUNT(*) INTO pointer_chunks_without_matching_book_chunk
    FROM rag_document_chunks ch
    WHERE ch.doc_type = 'course'
      AND ch.metadata->>'source_book_id' IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM rag_document_chunks source_chunk
          WHERE source_chunk.doc_type = 'book'
            AND source_chunk.doc_id::text = ch.metadata->>'source_book_id'
            AND source_chunk.chunk_index = ch.chunk_index
            AND source_chunk.content = ch.content
      );

    IF pointer_chunks_without_attachment_source <> 0 THEN
        RAISE EXCEPTION 'migration 055: % book-pointer chunks have no course_documents attachment source',
            pointer_chunks_without_attachment_source;
    END IF;
    IF pointer_chunks_without_matching_book_chunk <> 0 THEN
        RAISE EXCEPTION 'migration 055: % book-pointer chunks are not proven duplicate book chunks',
            pointer_chunks_without_matching_book_chunk;
    END IF;
END $$;

-- Snapshot the inputs so the final verification can assert exact deltas.
CREATE TEMP TABLE _mig055_before ON COMMIT DROP AS
SELECT
    (SELECT COUNT(*) FROM rag_document_chunks) AS total_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks WHERE doc_type = 'course') AS course_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks
      WHERE doc_type = 'course' AND metadata->>'source_book_id' IS NOT NULL) AS pointer_copy_chunks,
    (SELECT COUNT(*) FROM rag_document_chunks WHERE doc_type = 'book') AS book_chunks,
    (SELECT COUNT(*) FROM course_documents WHERE book_id IS NOT NULL) AS pointer_rows,
    (SELECT COUNT(*) FROM course_documents WHERE book_id IS NULL) AS discarded_direct_rows;

-- 1) Book-pointer rows -> attachments.
INSERT INTO course_attachments (course_id, book_id)
SELECT cd.course_id, cd.book_id
FROM course_documents cd
WHERE cd.book_id IS NOT NULL
ON CONFLICT (course_id, book_id) DO NOTHING;

-- 2) Drop all old course-owned chunks. Direct chunks are legacy local sources
-- being intentionally retired; pointer chunks were preflighted as duplicates.
DELETE FROM rag_document_chunks WHERE doc_type = 'course';

-- 3) Verify exact deltas before dropping anything; abort the whole transaction
-- on any mismatch.
DO $$
DECLARE
    before RECORD;
    after_total BIGINT;
    after_course BIGINT;
    after_book BIGINT;
    after_course_id_keys BIGINT;
    missing_pointer_attachments BIGINT;
BEGIN
    SELECT * INTO before FROM _mig055_before;

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

    IF after_course <> 0 THEN
        RAISE EXCEPTION 'migration 055: % doc_type=course chunks remain', after_course;
    END IF;
    IF after_course_id_keys <> 0 THEN
        RAISE EXCEPTION 'migration 055: % chunks still carry a course_id metadata key', after_course_id_keys;
    END IF;
    IF missing_pointer_attachments <> 0 THEN
        RAISE EXCEPTION 'migration 055: % book-pointer rows missing attachments', missing_pointer_attachments;
    END IF;
    IF after_book <> before.book_chunks THEN
        RAISE EXCEPTION 'migration 055: book chunks % do not equal prior %',
            after_book, before.book_chunks;
    END IF;
    IF after_total <> before.total_chunks - before.course_chunks THEN
        RAISE EXCEPTION 'migration 055: total chunks % do not match expected % (before %, course %)',
            after_total, before.total_chunks - before.course_chunks, before.total_chunks, before.course_chunks;
    END IF;

    RAISE NOTICE 'migration 055: pointer_rows=% discarded_direct_rows=% deleted_chunks=%',
        before.pointer_rows, before.discarded_direct_rows, before.course_chunks;
END $$;

-- 4) Retire the table and its dead chunk index.
DROP TABLE course_documents;
DROP INDEX IF EXISTS rag_document_chunks_metadata_course_id_idx;
