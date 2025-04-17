from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field


class OnboardingQuestion(BaseModel):
    """Schema for an onboarding question."""

    question: str
    type: Literal["multiple_choice", "text"] = "multiple_choice"
    options: list[str] | None = None

class OnboardingResponse(BaseModel):
    """Schema for user's response to an onboarding question."""

    question: str
    answer: str

class OnboardingRequest(BaseModel):
    """Schema for initiating the onboarding process."""

    topic: str = Field(
        default=...,
        description="The topic the user wants to learn",
        examples=["machine learning"],
    )

    class Config:
        """Configuration for the OnboardingRequest schema."""

        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "topic": "machine learning",
            },
        }

class OnboardingQuestions(BaseModel):
    """Schema for the list of onboarding questions."""

    questions: list[OnboardingQuestion]
