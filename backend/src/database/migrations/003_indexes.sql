-- autocommit
-- indexes.sql
-- Concurrent indexes for foreign keys and common filters

CREATE INDEX IF NOT EXISTS courses_user_id_idx ON courses(user_id);
CREATE INDEX IF NOT EXISTS lessons_course_id_idx ON lessons(course_id);
CREATE INDEX IF NOT EXISTS lessons_course_module_order_idx ON lessons(course_id, module_order, "order");
CREATE INDEX IF NOT EXISTS course_documents_course_id_idx ON course_documents(course_id);

CREATE INDEX IF NOT EXISTS books_user_id_idx ON books(user_id);

CREATE INDEX IF NOT EXISTS videos_user_id_idx ON videos(user_id);
CREATE INDEX IF NOT EXISTS video_chapters_video_id_idx ON video_chapters(video_id);

CREATE INDEX IF NOT EXISTS highlights_user_id_idx ON highlights(user_id);
CREATE INDEX IF NOT EXISTS highlights_content_idx ON highlights(content_type, content_id);

CREATE INDEX IF NOT EXISTS tags_name_idx ON tags(name);
CREATE INDEX IF NOT EXISTS tag_associations_tag_id_idx ON tag_associations(tag_id);
CREATE INDEX IF NOT EXISTS tag_associations_user_id_idx ON tag_associations(user_id);
CREATE INDEX IF NOT EXISTS tag_associations_content_idx ON tag_associations(content_type, content_id);

CREATE INDEX IF NOT EXISTS user_progress_user_id_idx ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS user_progress_user_type_idx ON user_progress(user_id, content_type);
CREATE INDEX IF NOT EXISTS user_progress_content_idx ON user_progress(content_id);
CREATE INDEX IF NOT EXISTS ai_custom_instructions_user_id_idx ON ai_custom_instructions(user_id);

CREATE UNIQUE INDEX IF NOT EXISTS rag_document_chunks_doc_id_chunk_index_idx ON rag_document_chunks (doc_id, chunk_index);
CREATE INDEX IF NOT EXISTS rag_document_chunks_doc_type_idx ON rag_document_chunks (doc_type);
CREATE INDEX IF NOT EXISTS rag_document_chunks_metadata_course_id_idx ON rag_document_chunks ((metadata->>'course_id'));

CREATE INDEX IF NOT EXISTS course_concepts_concept_id_idx ON course_concepts(concept_id);
CREATE INDEX IF NOT EXISTS concept_prerequisites_prereq_id_idx ON concept_prerequisites(prereq_id);
CREATE INDEX IF NOT EXISTS concept_similarities_concept_b_id_idx ON concept_similarities(concept_b_id);
CREATE INDEX IF NOT EXISTS probe_events_concept_id_idx ON probe_events(concept_id);
CREATE INDEX IF NOT EXISTS user_concept_state_concept_id_idx ON user_concept_state(concept_id);

-- Adaptive / scheduling hot paths
CREATE INDEX IF NOT EXISTS user_concept_state_user_id_idx ON user_concept_state(user_id);
CREATE INDEX IF NOT EXISTS user_concept_state_next_review_at_idx ON user_concept_state(next_review_at);
CREATE INDEX IF NOT EXISTS probe_events_user_ts_idx ON probe_events(user_id, ts);
