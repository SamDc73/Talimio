"""Durable learner memory: profile lane (user slots) and pedagogy lane (course teaching state).

This namespace re-exports the cross-module entry points; everything else under
``services/`` is lane-internal. Two deliberate omissions: ``notes_search``
imports the RAG stack, so its one consumer lazy-imports the deep path, and the
job task bodies in ``src.jobs.tasks`` lazy-import lane internals directly.
"""

from src.memory.services.pedagogy_service import build_pedagogy_context
from src.memory.services.profile_maintenance import advance_watermark_past_history, defer_profile_maintenance
from src.memory.services.profile_service import (
    SlotCommitResult,
    build_memory_context,
    clear_slot,
    redact_slot_evidence,
    set_slot,
)
from src.memory.services.teaching_events import record_teaching_event


__all__ = [
    "SlotCommitResult",
    "advance_watermark_past_history",
    "build_memory_context",
    "build_pedagogy_context",
    "clear_slot",
    "defer_profile_maintenance",
    "record_teaching_event",
    "redact_slot_evidence",
    "set_slot",
]
