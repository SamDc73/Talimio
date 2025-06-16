"""Database migrations module."""

from .missing_columns import run_all_missing_columns_migrations
from .tagging_columns import run_tagging_migrations
from .user_table import add_user_table
from .video_uuid import add_video_uuid_column


__all__ = [
    "add_user_table",
    "add_video_uuid_column",
    "run_all_missing_columns_migrations",
    "run_tagging_migrations",
]
