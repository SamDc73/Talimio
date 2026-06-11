"""Facade entrypoint for learning capability execution."""

import uuid
from collections.abc import Awaitable, Callable, Mapping

from pydantic import BaseModel  # noqa: TID251 - not an HTTP schema
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.facade import CoursesFacade
from src.learning_capabilities import capability_registry
from src.learning_capabilities.errors import LearningCapabilitiesBadRequestError
from src.learning_capabilities.schemas import (
    AppendCourseLessonCapabilityInput,
    AppendCourseLessonCapabilityOutput,
    AttachBookToCourseCapabilityInput,
    AttachBookToCourseCapabilityOutput,
    BuildContextBundleCapabilityInput,
    BuildContextBundleCapabilityOutput,
    CapabilityDescriptor,
    CreateCourseCapabilityInput,
    CreateCourseCapabilityOutput,
    DetachBookFromCourseCapabilityInput,
    DetachBookFromCourseCapabilityOutput,
    ExtendLessonWithContextCapabilityInput,
    GenerateConceptProbeCapabilityInput,
    GenerateConceptProbeCapabilityOutput,
    GetConceptTutorContextCapabilityInput,
    GetConceptTutorContextCapabilityOutput,
    GetCourseFrontierCapabilityInput,
    GetCourseFrontierCapabilityOutput,
    GetCourseOutlineStateCapabilityInput,
    GetCourseOutlineStateCapabilityOutput,
    GetCourseStateCapabilityInput,
    GetCourseStateCapabilityOutput,
    GetLessonStateCapabilityInput,
    GetLessonStateCapabilityOutput,
    GetLessonWindowsCapabilityInput,
    GetLessonWindowsCapabilityOutput,
    LessonMutationCapabilityOutput,
    ListBooksCapabilityInput,
    ListBooksCapabilityOutput,
    ListCourseAttachmentsCapabilityInput,
    ListCourseAttachmentsCapabilityOutput,
    ListRelevantCoursesCapabilityInput,
    ListRelevantCoursesCapabilityOutput,
    RegenerateLessonWithContextCapabilityInput,
    SearchBooksCapabilityInput,
    SearchBooksCapabilityOutput,
    SearchConceptsCapabilityInput,
    SearchConceptsCapabilityOutput,
    SearchCourseSourcesCapabilityInput,
    SearchCourseSourcesCapabilityOutput,
    SearchLessonsCapabilityInput,
    SearchLessonsCapabilityOutput,
    SubmitConceptProbeResultCapabilityInput,
    SubmitConceptProbeResultCapabilityOutput,
)
from src.learning_capabilities.services.action_service import LearningCapabilityActionService
from src.learning_capabilities.services.authorization_service import LearningCapabilityAuthorizationService
from src.learning_capabilities.services.context_packet_service import LearningContextPacketService
from src.learning_capabilities.services.query_service import LearningCapabilityQueryService


# Dispatch tables erase per-capability types; inputs are validated by the
# paired model before the handler runs.
type _CapabilityHandler = Callable[..., Awaitable[BaseModel]]


class LearningCapabilitiesFacade:  # noqa: PLR0904
    """Single typed entrypoint for learning capabilities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        authorization_service = LearningCapabilityAuthorizationService(session)
        self._query_service = LearningCapabilityQueryService(session)
        self._action_service = LearningCapabilityActionService(
            session,
            authorization_service=authorization_service,
            course_capability_port=CoursesFacade(session),
        )
        self._context_packet_service = LearningContextPacketService(self._query_service)

    def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return the stable capability registry."""
        return capability_registry.list_capabilities()

    def get_capability(self, name: str) -> CapabilityDescriptor | None:
        """Return one capability descriptor."""
        return capability_registry.get_capability(name)

    async def search_lessons(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchLessonsCapabilityInput,
    ) -> SearchLessonsCapabilityOutput:
        """Execute `search_lessons` capability."""
        return await self._query_service.search_lessons(user_id=user_id, payload=payload)

    async def list_relevant_courses(
        self,
        *,
        user_id: uuid.UUID,
        payload: ListRelevantCoursesCapabilityInput,
    ) -> ListRelevantCoursesCapabilityOutput:
        """Execute `list_relevant_courses` capability."""
        return await self._query_service.list_relevant_courses(user_id=user_id, payload=payload)

    async def search_concepts(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchConceptsCapabilityInput,
    ) -> SearchConceptsCapabilityOutput:
        """Execute `search_concepts` capability."""
        return await self._query_service.search_concepts(user_id=user_id, payload=payload)

    async def search_course_sources(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchCourseSourcesCapabilityInput,
    ) -> SearchCourseSourcesCapabilityOutput:
        """Execute `search_course_sources` capability."""
        return await self._query_service.search_course_sources(user_id=user_id, payload=payload)

    async def search_books(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchBooksCapabilityInput,
    ) -> SearchBooksCapabilityOutput:
        """Execute `search_books` capability."""
        return await self._query_service.search_books(user_id=user_id, payload=payload)

    async def list_books(
        self,
        *,
        user_id: uuid.UUID,
        payload: ListBooksCapabilityInput,
    ) -> ListBooksCapabilityOutput:
        """Execute `list_books` capability."""
        return await self._query_service.list_books(user_id=user_id, payload=payload)

    async def list_course_attachments(
        self,
        *,
        user_id: uuid.UUID,
        payload: ListCourseAttachmentsCapabilityInput,
    ) -> ListCourseAttachmentsCapabilityOutput:
        """Execute `list_course_attachments` capability."""
        return await self._query_service.list_course_attachments(user_id=user_id, payload=payload)

    async def attach_book_to_course(
        self,
        *,
        user_id: uuid.UUID,
        payload: AttachBookToCourseCapabilityInput,
    ) -> AttachBookToCourseCapabilityOutput:
        """Execute `attach_book_to_course` capability."""
        return await self._action_service.attach_book_to_course(user_id=user_id, payload=payload)

    async def detach_book_from_course(
        self,
        *,
        user_id: uuid.UUID,
        payload: DetachBookFromCourseCapabilityInput,
    ) -> DetachBookFromCourseCapabilityOutput:
        """Execute `detach_book_from_course` capability."""
        return await self._action_service.detach_book_from_course(user_id=user_id, payload=payload)

    async def get_course_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseStateCapabilityInput,
    ) -> GetCourseStateCapabilityOutput:
        """Execute `get_course_state` capability."""
        return await self._query_service.get_course_state(user_id=user_id, payload=payload)

    async def get_course_outline_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseOutlineStateCapabilityInput,
    ) -> GetCourseOutlineStateCapabilityOutput:
        """Execute `get_course_outline_state` capability."""
        return await self._query_service.get_course_outline_state(user_id=user_id, payload=payload)

    async def get_lesson_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetLessonStateCapabilityInput,
    ) -> GetLessonStateCapabilityOutput:
        """Execute `get_lesson_state` capability."""
        return await self._query_service.get_lesson_state(user_id=user_id, payload=payload)

    async def get_lesson_windows(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetLessonWindowsCapabilityInput,
    ) -> GetLessonWindowsCapabilityOutput:
        """Execute `get_lesson_windows` capability."""
        return await self._query_service.get_lesson_windows(user_id=user_id, payload=payload)

    async def get_concept_tutor_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetConceptTutorContextCapabilityInput,
    ) -> GetConceptTutorContextCapabilityOutput:
        """Execute `get_concept_tutor_context` capability."""
        return await self._query_service.get_concept_tutor_context(user_id=user_id, payload=payload)

    async def get_course_frontier(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseFrontierCapabilityInput,
    ) -> GetCourseFrontierCapabilityOutput:
        """Execute `get_course_frontier` capability."""
        return await self._query_service.get_course_frontier(user_id=user_id, payload=payload)

    async def build_context_bundle(
        self,
        *,
        user_id: uuid.UUID,
        payload: BuildContextBundleCapabilityInput,
    ) -> BuildContextBundleCapabilityOutput:
        """Execute `build_context_bundle` capability."""
        return await self._context_packet_service.build_context_bundle(user_id=user_id, payload=payload)

    async def create_course(
        self,
        *,
        user_id: uuid.UUID,
        payload: CreateCourseCapabilityInput,
    ) -> CreateCourseCapabilityOutput:
        """Execute `create_course` capability."""
        return await self._action_service.create_course(user_id=user_id, payload=payload)

    async def append_course_lesson(
        self,
        *,
        user_id: uuid.UUID,
        payload: AppendCourseLessonCapabilityInput,
    ) -> AppendCourseLessonCapabilityOutput:
        """Execute `append_course_lesson` capability."""
        return await self._action_service.append_course_lesson(user_id=user_id, payload=payload)

    async def extend_lesson_with_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: ExtendLessonWithContextCapabilityInput,
    ) -> LessonMutationCapabilityOutput:
        """Execute `extend_lesson_with_context` capability."""
        return await self._action_service.extend_lesson_with_context(user_id=user_id, payload=payload)

    async def regenerate_lesson_with_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: RegenerateLessonWithContextCapabilityInput,
    ) -> LessonMutationCapabilityOutput:
        """Execute `regenerate_lesson_with_context` capability."""
        return await self._action_service.regenerate_lesson_with_context(user_id=user_id, payload=payload)

    async def generate_concept_probe(
        self,
        *,
        user_id: uuid.UUID,
        payload: GenerateConceptProbeCapabilityInput,
    ) -> GenerateConceptProbeCapabilityOutput:
        """Execute `generate_concept_probe` capability."""
        return await self._action_service.generate_concept_probe(user_id=user_id, payload=payload)

    async def submit_concept_probe_result(
        self,
        *,
        user_id: uuid.UUID,
        payload: SubmitConceptProbeResultCapabilityInput,
    ) -> SubmitConceptProbeResultCapabilityOutput:
        """Execute `submit_concept_probe_result` capability."""
        return await self._action_service.submit_concept_probe_result(user_id=user_id, payload=payload)

    async def execute_read_capability(
        self,
        *,
        user_id: uuid.UUID,
        capability_name: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Execute a read capability by name."""
        read_dispatch: dict[str, tuple[type[BaseModel], _CapabilityHandler]] = {
            "search_lessons": (SearchLessonsCapabilityInput, self.search_lessons),
            "search_concepts": (SearchConceptsCapabilityInput, self.search_concepts),
            "search_course_sources": (SearchCourseSourcesCapabilityInput, self.search_course_sources),
            "list_relevant_courses": (ListRelevantCoursesCapabilityInput, self.list_relevant_courses),
            "search_books": (SearchBooksCapabilityInput, self.search_books),
            "list_books": (ListBooksCapabilityInput, self.list_books),
            "list_course_attachments": (ListCourseAttachmentsCapabilityInput, self.list_course_attachments),
            "get_course_state": (GetCourseStateCapabilityInput, self.get_course_state),
            "get_course_outline_state": (GetCourseOutlineStateCapabilityInput, self.get_course_outline_state),
            "get_lesson_state": (GetLessonStateCapabilityInput, self.get_lesson_state),
            "get_lesson_windows": (GetLessonWindowsCapabilityInput, self.get_lesson_windows),
            "get_concept_tutor_context": (GetConceptTutorContextCapabilityInput, self.get_concept_tutor_context),
            "get_course_frontier": (GetCourseFrontierCapabilityInput, self.get_course_frontier),
            "build_context_bundle": (BuildContextBundleCapabilityInput, self.build_context_bundle),
        }
        entry = read_dispatch.get(capability_name)
        if entry is None:
            detail = f"Unknown read capability '{capability_name}'"
            raise LearningCapabilitiesBadRequestError(detail)
        input_model, handler = entry
        result = await handler(user_id=user_id, payload=input_model.model_validate(payload))
        return result.model_dump(by_alias=True, mode="json")

    async def execute_action_capability(
        self,
        *,
        user_id: uuid.UUID,
        capability_name: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Execute a write capability by name."""
        action_dispatch: dict[str, tuple[type[BaseModel], _CapabilityHandler]] = {
            "create_course": (CreateCourseCapabilityInput, self.create_course),
            "attach_book_to_course": (AttachBookToCourseCapabilityInput, self.attach_book_to_course),
            "detach_book_from_course": (DetachBookFromCourseCapabilityInput, self.detach_book_from_course),
            "append_course_lesson": (AppendCourseLessonCapabilityInput, self.append_course_lesson),
            "extend_lesson_with_context": (ExtendLessonWithContextCapabilityInput, self.extend_lesson_with_context),
            "regenerate_lesson_with_context": (
                RegenerateLessonWithContextCapabilityInput,
                self.regenerate_lesson_with_context,
            ),
            "generate_concept_probe": (GenerateConceptProbeCapabilityInput, self.generate_concept_probe),
            "submit_concept_probe_result": (
                SubmitConceptProbeResultCapabilityInput,
                self.submit_concept_probe_result,
            ),
        }
        entry = action_dispatch.get(capability_name)
        if entry is None:
            detail = f"Unknown action capability '{capability_name}'"
            raise LearningCapabilitiesBadRequestError(detail)
        input_model, handler = entry
        result = await handler(user_id=user_id, payload=input_model.model_validate(payload))
        return result.model_dump(by_alias=True, mode="json")
