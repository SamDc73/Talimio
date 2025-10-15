import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { api } from "@/lib/api"

/**
 * Hook for submitting quiz results to the backend for adaptive learning.
 *
 * The backend will:
 * 1. Analyze the quiz results with AI
 * 2. Store learning patterns in memory
 * 3. Adapt future lessons based on weak concepts
 *
 * @example
 * const { submitQuiz, isSubmitting } = useQuizSubmission();
 *
 * // When user completes a quiz:
 * const results = await submitQuiz({
 *   courseId: 'uuid-here',
 *   lessonId: 'uuid-here',
 *   questions: [
 *     {
 *       question: "What is React?",
 *       user_answer: "A library",
 *       correct_answer: "A JavaScript library for building UIs",
 *       is_correct: false,
 *       concept: "React fundamentals",
 *       explanation: "React is specifically for building user interfaces"
 *     }
 *   ],
 *   totalScore: 75.5,
 *   timeSpent: 300 // seconds
 * });
 */
export function useQuizSubmission() {
	const [lastSubmission, setLastSubmission] = useState(null)

	const mutation = useMutation({
		mutationFn: async ({ courseId, lessonId, questions, totalScore, timeSpent }) => {
			// Submit to the new quiz endpoint
			const response = await api.post(`/api/v1/courses/${courseId}/lessons/${lessonId}/quiz`, {
				lesson_id: lessonId,
				questions,
				total_score: totalScore,
				time_spent: timeSpent,
			})
			return response.data
		},
		onSuccess: (data) => {
			setLastSubmission(data)

			// Show feedback to user
			if (data.next_lesson_adapted) {
			} else {
			}
		},
		onError: (_error) => {},
	})

	return {
		submitQuiz: mutation.mutate,
		submitQuizAsync: mutation.mutateAsync,
		isSubmitting: mutation.isPending,
		lastSubmission,
		performanceSummary: lastSubmission?.performance_summary,
		reset: () => {
			mutation.reset()
			setLastSubmission(null)
		},
	}
}

/**
 * Helper function to format quiz questions for submission
 * Useful when quiz data comes from different sources
 */
export function formatQuizQuestions(rawQuestions) {
	return rawQuestions.map((q) => ({
		question: q.question || q.text || "",
		user_answer: q.userAnswer || q.selected || "",
		correct_answer: q.correctAnswer || q.correct || "",
		is_correct: q.isCorrect !== undefined ? q.isCorrect : q.userAnswer === q.correctAnswer,
		concept: q.concept || q.topic || q.category || "general",
		explanation: q.explanation || q.feedback || "",
	}))
}

/**
 * Helper to calculate total score from questions
 */
export function calculateQuizScore(questions) {
	if (!questions || questions.length === 0) return 0

	const correct = questions.filter((q) => q.is_correct || q.isCorrect).length
	return (correct / questions.length) * 100
}
