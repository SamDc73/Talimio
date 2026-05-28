-- Drop legacy image rows from course_documents.
-- Images are now inlined as base64 data URLs into the course-generation
-- LLM prompt and never persisted. Existing rows have no operational use:
-- their `status='embedded'` was synthetic (no chunks were ever embedded)
-- and their `file_path` points at local disk that does not survive cloud
-- container restarts. Local-dev orphans under {LOCAL_STORAGE_PATH}/rag_documents/
-- can be cleaned manually if desired.
DELETE FROM course_documents WHERE document_type = 'image';
