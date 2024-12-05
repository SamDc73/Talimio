from src.ai.client import ModelManager
from src.onboarding.schemas import OnboardingQuestion, OnboardingQuestions


class OnboardingService:
    """Service for handling the onboarding process."""

    def __init__(self) -> None:
        self.ai_client = ModelManager()

    async def generate_questions(self, topic: str) -> OnboardingQuestions:
        """Generate onboarding questions based on the topic."""
        prompt = f"""Generate 5 multiple choice questions to understand a user's background and goals in learning {topic}.
        Each question should help personalize their learning journey.
        Return the response in this exact JSON format:
        [
            {{
                "question": "What is your current experience level with {topic}?",
                "options": ["Beginner", "Intermediate", "Advanced"]
            }},
            ...
        ]
        Make sure each question has 3-4 relevant and diverse options."""

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer. Always respond with valid JSON arrays containing question objects."},
            {"role": "user", "content": prompt}
        ]

        # Get completion from AI client
        try:
            content = await self.ai_client._get_completion(messages)
            if content is None:
                raise ValueError("No content received from AI")

            # Strip any potential markdown code block markers
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            import json
            questions_data = json.loads(content)
            if not isinstance(questions_data, list):
                raise ValueError("Response must be a JSON array")

            questions = []
            for q in questions_data:
                if not isinstance(q, dict) or "question" not in q or "options" not in q:
                    raise ValueError("Each question must have 'question' and 'options' fields")
                if not isinstance(q["options"], list):
                    raise ValueError("Options must be an array")
                
                questions.append(
                    OnboardingQuestion(
                        question=q["question"],
                        type="multiple_choice",
                        options=q["options"]
                    )
                )

            return OnboardingQuestions(questions=questions)
        except Exception as e:
            raise ValueError(f"Failed to generate questions: {e!s}") from e
