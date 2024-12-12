from src.ai.client import ModelManager
from src.onboarding.schemas import OnboardingQuestion, OnboardingQuestions


class OnboardingService:
    """Service for handling the onboarding process."""

    def __init__(self) -> None:
        self.ai_client = ModelManager()

    async def generate_questions(self, topic: str) -> OnboardingQuestions:
        """Generate onboarding questions based on the topic."""
        prompt = f"""For someone wanting to learn {topic}, create 5 questions to understand their:
        1. Current experience level with {topic}
        2. Learning goals
        3. Preferred learning style
        4. Available time commitment
        5. Related skills/background

        Format as JSON array:
        [
            {{
                "question": "What is your current experience with {topic}?",
                "options": ["Complete Beginner", "Some Basic Knowledge", "Intermediate", "Advanced"]
            }}
        ]"""

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]

        try:
            questions_data = await self.ai_client._get_completion(messages)

            # Validate and transform the data
            questions = []
            for q in questions_data:
                if not isinstance(q, dict) or "question" not in q or "options" not in q:
                    raise ValueError("Each question must have 'question' and 'options' fields")

                questions.append(
                    OnboardingQuestion(question=q["question"], type="multiple_choice", options=q["options"])
                )

            return OnboardingQuestions(questions=questions)

        except Exception as e:
            raise ValueError(f"Failed to generate questions: {e}") from e
