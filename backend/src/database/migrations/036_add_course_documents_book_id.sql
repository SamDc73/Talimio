ALTER TABLE course_documents
ADD COLUMN book_id UUID REFERENCES books(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_course_documents_book_id ON course_documents(book_id);
