"""Static registry for learning capability metadata."""

from src.learning_capabilities.schemas import CapabilityDescriptor


_CAPABILITIES: tuple[CapabilityDescriptor, ...] = (
    CapabilityDescriptor(
        name="search_lessons",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Search lessons owned by the learner.",
    ),
    CapabilityDescriptor(
        name="list_relevant_courses",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="List courses most relevant to the latest learner message.",
    ),
    CapabilityDescriptor(
        name="search_concepts",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Search adaptive course concepts with learner-state signals.",
    ),
    CapabilityDescriptor(
        name="search_course_sources",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Search uploaded course source excerpts for one owned course.",
    ),
    CapabilityDescriptor(
        name="get_course_state",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Return compact course state with progress signals.",
    ),
    CapabilityDescriptor(
        name="get_course_outline_state",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Return compact per-lesson outline state for one course.",
    ),
    CapabilityDescriptor(
        name="get_lesson_state",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Return compact lesson state payload.",
    ),
    CapabilityDescriptor(
        name="get_lesson_windows",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Return compact window-level content for one lesson.",
    ),
    CapabilityDescriptor(
        name="get_course_frontier",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Return adaptive frontier state for a course.",
    ),
    CapabilityDescriptor(
        name="build_context_bundle",
        kind="read",
        requires_confirmation=False,
        public_api_eligible=True,
        description="Build compact assistant context packet from capability data.",
    ),
    CapabilityDescriptor(
        name="create_course",
        kind="write",
        requires_confirmation=True,
        public_api_eligible=True,
        description="Create a new course from a learner prompt.",
    ),
    CapabilityDescriptor(
        name="append_course_lesson",
        kind="write",
        requires_confirmation=True,
        public_api_eligible=True,
        description="Append a lesson to an existing course outline.",
    ),
    CapabilityDescriptor(
        name="extend_lesson_with_context",
        kind="write",
        requires_confirmation=True,
        public_api_eligible=True,
        description="Generate additional lesson content and append it to the lesson body.",
    ),
    CapabilityDescriptor(
        name="regenerate_lesson_with_context",
        kind="write",
        requires_confirmation=True,
        public_api_eligible=True,
        description="Regenerate lesson content with explicit injected context.",
    ),
)

_CAPABILITY_BY_NAME = {item.name: item for item in _CAPABILITIES}


def list_capabilities() -> tuple[CapabilityDescriptor, ...]:
    """Return all known capability descriptors."""
    return _CAPABILITIES


def get_capability(name: str) -> CapabilityDescriptor | None:
    """Return one capability descriptor by name."""
    return _CAPABILITY_BY_NAME.get(name)


def requires_confirmation(name: str) -> bool:
    """Return whether the capability requires confirmation before mutation."""
    descriptor = get_capability(name)
    return bool(descriptor and descriptor.requires_confirmation)
