from fastapi import APIRouter, HTTPException, status

from src.onboarding.schemas import OnboardingQuestions, OnboardingRequest
from src.onboarding.service import OnboardingService


router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post(
    "/questions",
    summary="Generate onboarding questions",
    description="Generate personalized onboarding questions based on the learning topic",
)
async def generate_onboarding_questions(
    request: OnboardingRequest,
) -> OnboardingQuestions:
    """Generate personalized onboarding questions."""
    service = OnboardingService()
    try:
        return await service.generate_questions(request.topic)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
