"""Slot vocabulary for durable user profile memory.

Slots favor stable cross-product preferences; volatile lesson- or course-local
wishes stay out of global profile memory (they belong to pedagogical memory).
Descriptions double as extraction guidance for the maintenance pass.
"""

from __future__ import annotations


PROFILE_SLOTS: dict[str, str] = {
    "content_modality": "Preferred learning content format overall, e.g. 'prefers video lessons' or 'text-first'.",
    "avoid_modality": "Content formats the user consistently wants less of, e.g. 'avoid long videos'.",
    "explanation_style": "How explanations should be written, e.g. 'analogy-first', 'example-driven', 'formal'.",
    "explanation_depth": "Preferred depth of detail, e.g. 'concise overviews' or 'thorough with edge cases'.",
    "video_summaries_default": "Whether the user wants video summaries by default, e.g. 'yes' or 'no'.",
    "primary_study_device": "Device the user usually studies on, e.g. 'phone' or 'laptop'.",
    "math_proof_style": "Preferred style for mathematical proofs, e.g. 'intuition before formalism'.",
    "code_explanation_style": "Preferred style for code explanations, e.g. 'commented snippets', 'step-by-step'.",
}


def is_known_slot(slot: str) -> bool:
    """Whether a slot name belongs to the supported vocabulary."""
    return slot in PROFILE_SLOTS
