from src.ai.client import ModelManager
from src.ai.prompts import ONBOARDING_QUESTIONS_PROMPT
from src.onboarding.schemas import OnboardingQuestion, OnboardingQuestions


class OnboardingService:
    """Service for handling the onboarding process."""

    def __init__(self) -> None:
        self.ai_client = ModelManager()

    async def generate_questions(self, topic: str) -> OnboardingQuestions:
        """Generate onboarding questions based on the topic."""
        prompt = ONBOARDING_QUESTIONS_PROMPT.format(topic=topic)

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]

        try:
            questions_data = await self.ai_client.get_completion(messages)

            # Validate and transform the data
            questions = []

            def _raise_invalid_question() -> None:
                msg = "Each question must have 'question' and 'options' fields"
                raise ValueError(msg)

            for q in questions_data:
                if not isinstance(q, dict) or "question" not in q or "options" not in q:
                    _raise_invalid_question()
                questions.append(
                    OnboardingQuestion(question=q["question"], type="multiple_choice", options=q["options"]),
                )

            return OnboardingQuestions(questions=questions)

        except Exception as e:
            msg = f"Failed to generate questions: {e}"
            raise ValueError(msg) from e
