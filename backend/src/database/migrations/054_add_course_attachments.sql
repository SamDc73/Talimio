-- Books ground courses through explicit attachment rows: a course is a list
-- of pointers to books, chunks stay owned by the book, and course-scoped RAG
-- search becomes a join. No enums, no role column, no visibility axis —
-- UNIQUE (course_id, book_id) is the whole contract. Videos land later as a
-- nullable video_id column on this same table, not as a new table.
CREATE TABLE IF NOT EXISTS course_attachments (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (course_id, book_id)
);

-- The UNIQUE constraint already indexes (course_id, book_id) for course-side
-- lookups; book-side lookups (delete conflict check, FK cascade) need their own.
CREATE INDEX IF NOT EXISTS course_attachments_book_id_idx ON course_attachments (book_id);
