"""Re-export Progress model from courses for compatibility."""

from src.courses.models import LessonProgress as Progress


__all__ = ["Progress"]
