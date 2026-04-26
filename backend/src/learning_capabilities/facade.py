"""Facade entrypoint for learning capability execution."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.learning_capabilities import capability_registry
from src.learning_capabilities.errors import LearningCapabilitiesBadRequestError
from src.learning_capabilities.schemas import (
    AppendCourseLessonCapabilityInput,
    AppendCourseLessonCapabilityOutput,
    BuildContextBundleCapabilityInput,
    BuildContextBundleCapabilityOutput,
    CapabilityDescriptor,
    CreateCourseCapabilityInput,
    CreateCourseCapabilityOutput,
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
    ListRelevantCoursesCapabilityInput,
    ListRelevantCoursesCapabilityOutput,
    RegenerateLessonWithContextCapabilityInput,
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


class LearningCapabilitiesFacade:  # noqa: PLR0904
    """Single typed entrypoint for learning capabilities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        authorization_service = LearningCapabilityAuthorizationService(session)
        self._query_service = LearningCapabilityQueryService(session)
        self._action_service = LearningCapabilityActionService(
            session,
            authorization_service=authorization_service,
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
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a read capability by name."""
        if capability_name == "search_lessons":
            result = await self.search_lessons(
                user_id=user_id,
                payload=SearchLessonsCapabilityInput.model_validate(payload),
            )
        elif capability_name == "search_concepts":
            result = await self.search_concepts(
                user_id=user_id,
                payload=SearchConceptsCapabilityInput.model_validate(payload),
            )
        elif capability_name == "search_course_sources":
            result = await self.search_course_sources(
                user_id=user_id,
                payload=SearchCourseSourcesCapabilityInput.model_validate(payload),
            )
        elif capability_name == "list_relevant_courses":
            result = await self.list_relevant_courses(
                user_id=user_id,
                payload=ListRelevantCoursesCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_course_state":
            result = await self.get_course_state(
                user_id=user_id,
                payload=GetCourseStateCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_course_outline_state":
            result = await self.get_course_outline_state(
                user_id=user_id,
                payload=GetCourseOutlineStateCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_lesson_state":
            result = await self.get_lesson_state(
                user_id=user_id,
                payload=GetLessonStateCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_lesson_windows":
            result = await self.get_lesson_windows(
                user_id=user_id,
                payload=GetLessonWindowsCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_concept_tutor_context":
            result = await self.get_concept_tutor_context(
                user_id=user_id,
                payload=GetConceptTutorContextCapabilityInput.model_validate(payload),
            )
        elif capability_name == "get_course_frontier":
            result = await self.get_course_frontier(
                user_id=user_id,
                payload=GetCourseFrontierCapabilityInput.model_validate(payload),
            )
        elif capability_name == "build_context_bundle":
            result = await self.build_context_bundle(
                user_id=user_id,
                payload=BuildContextBundleCapabilityInput.model_validate(payload),
            )
        else:
            detail = f"Unknown read capability '{capability_name}'"
            raise LearningCapabilitiesBadRequestError(detail)
        return result.model_dump(by_alias=True, mode="json")

    async def execute_action_capability(
        self,
        *,
        user_id: uuid.UUID,
        capability_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a write capability by name."""
        if capability_name == "create_course":
            result = await self.create_course(
                user_id=user_id,
                payload=CreateCourseCapabilityInput.model_validate(payload),
            )
        elif capability_name == "append_course_lesson":
            result = await self.append_course_lesson(
                user_id=user_id,
                payload=AppendCourseLessonCapabilityInput.model_validate(payload),
            )
        elif capability_name == "extend_lesson_with_context":
            result = await self.extend_lesson_with_context(
                user_id=user_id,
                payload=ExtendLessonWithContextCapabilityInput.model_validate(payload),
            )
        elif capability_name == "regenerate_lesson_with_context":
            result = await self.regenerate_lesson_with_context(
                user_id=user_id,
                payload=RegenerateLessonWithContextCapabilityInput.model_validate(payload),
            )
        elif capability_name == "generate_concept_probe":
            result = await self.generate_concept_probe(
                user_id=user_id,
                payload=GenerateConceptProbeCapabilityInput.model_validate(payload),
            )
        elif capability_name == "submit_concept_probe_result":
            result = await self.submit_concept_probe_result(
                user_id=user_id,
                payload=SubmitConceptProbeResultCapabilityInput.model_validate(payload),
            )
        else:
            detail = f"Unknown action capability '{capability_name}'"
            raise LearningCapabilitiesBadRequestError(detail)
        return result.model_dump(by_alias=True, mode="json")
