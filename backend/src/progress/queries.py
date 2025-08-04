"""Optimized SQL queries for progress operations."""


# SQLAlchemy with asyncpg doesn't support ::type casting in parameters
# We cast to UUID in the service layer instead

GET_BATCH_PROGRESS_QUERY = """
SELECT content_id, progress_percentage, metadata
FROM user_progress
WHERE user_id = :user_id
AND content_id = ANY(:content_ids)
"""

UPSERT_PROGRESS_QUERY = """
INSERT INTO user_progress (user_id, content_id, content_type, progress_percentage, metadata)
VALUES (:user_id, :content_id, :content_type, :progress_percentage, CAST(:metadata AS jsonb))
ON CONFLICT (user_id, content_id)
DO UPDATE SET
    progress_percentage = EXCLUDED.progress_percentage,
    metadata = EXCLUDED.metadata,
    updated_at = NOW()
RETURNING id, user_id, content_id, content_type, progress_percentage, metadata, created_at, updated_at
"""

GET_SINGLE_PROGRESS_QUERY = """
SELECT id, user_id, content_id, content_type, progress_percentage, metadata, created_at, updated_at
FROM user_progress
WHERE user_id = :user_id
AND content_id = :content_id
"""

DELETE_PROGRESS_QUERY = """
DELETE FROM user_progress
WHERE user_id = :user_id
AND content_id = :content_id
"""
