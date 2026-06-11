-- Highlight payloads are validated Pydantic models dumped into the
-- highlights.highlight_data JSONB column. The dump now serializes by alias
-- (camelCase) so the stored blob matches the camelCase wire contract that
-- surfaces it inside HighlightResponse.highlightData. Rename the multi-word
-- keys in existing rows so old and new blobs read the same; single-word keys
-- (text, page, position, color, note, cfi, chapter, speaker) are unaffected.

UPDATE highlights
SET highlight_data = (highlight_data - 'start_time') || jsonb_build_object('startTime', highlight_data->'start_time')
WHERE highlight_data ? 'start_time';

UPDATE highlights
SET highlight_data = (highlight_data - 'end_time') || jsonb_build_object('endTime', highlight_data->'end_time')
WHERE highlight_data ? 'end_time';

UPDATE highlights
SET highlight_data = (highlight_data - 'transcript_index') || jsonb_build_object('transcriptIndex', highlight_data->'transcript_index')
WHERE highlight_data ? 'transcript_index';

UPDATE highlights
SET highlight_data = (highlight_data - 'spine_index') || jsonb_build_object('spineIndex', highlight_data->'spine_index')
WHERE highlight_data ? 'spine_index';
