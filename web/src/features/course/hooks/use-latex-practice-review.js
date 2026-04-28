import { useCallback, useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import logger from "@/lib/logger"

const normalizeAttempts = (attempts) => {
	if (!Number.isInteger(attempts) || attempts <= 0) {
		throw new Error("attempts must be a positive integer")
	}
	return attempts
}

const normalizeDuration = (durationMs) => {
	if (typeof durationMs !== "number" || !Number.isFinite(durationMs) || durationMs < 0) {
		throw new Error("durationMs must be a non-negative number")
	}
	return Math.round(durationMs)
}

const normalizeHintsUsed = (hintsUsed) => {
	if (!Number.isInteger(hintsUsed) || hintsUsed < 0) {
		throw new Error("hintsUsed must be a non-negative integer")
	}
	return hintsUsed
}

export function useLatexPracticeReview({
	courseId,
	lessonId,
	conceptId: initialConceptId = null,
	practiceContext = "inline",
} = {}) {
	const courseService = useCourseService(courseId)

	const [isSubmitting, setIsSubmitting] = useState(false)
	const [error, setError] = useState(null)

	const resolveConceptId = useCallback(
		(targetConceptId) => {
			const concept = targetConceptId ?? initialConceptId
			if (!concept) {
				throw new Error("Concept ID required for practice review submission")
			}
			return concept
		},
		[initialConceptId]
	)

	const submitAttempt = useCallback(
		async ({ questionId, answerText, hintsUsed, durationMs }) => {
			if (!courseId) {
				throw new Error("Course ID required for practice attempt")
			}
			if (!questionId) {
				throw new Error("Question ID required for practice attempt")
			}

			const attempt = await courseService.submitAttempt({
				attemptId: crypto.randomUUID(),
				questionId,
				learnerAnswer: answerText,
				hintsUsed,
				durationMs,
			})
			return { grade: attempt, attempt, rating: null, review: null }
		},
		[courseId, courseService]
	)

	const submitAnswer = useCallback(
		async ({
			questionId,
			question,
			expectedAnswer,
			answerKind = "math_latex",
			criteria,
			answerText,
			conceptId,
			attempts,
			durationMs,
			hintsUsed,
			practiceContext: contextOverride,
		} = {}) => {
			normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)

			if (questionId) {
				setIsSubmitting(true)
				setError(null)
				try {
					return await submitAttempt({
						questionId,
						answerText,
						hintsUsed: normalizedHints,
						durationMs: normalizedDuration,
					})
				} catch (submissionError) {
					setError(submissionError)
					logger.error("Failed to submit practice attempt", submissionError, {
						courseId,
						lessonId,
						conceptId: conceptId ?? initialConceptId,
						questionId,
					})
					throw submissionError
				} finally {
					setIsSubmitting(false)
				}
			}

			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for practice grading")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			const contextValue = contextOverride || practiceContext

			let payload = null
			if (contextValue === "drill") {
				payload = {
					kind: "practice_answer",
					question,
					expected: {
						expectedAnswer,
						answerKind,
						criteria,
					},
					answer: {
						answerText,
					},
					context: {
						courseId,
						lessonId,
						conceptId: resolvedConceptId,
						practiceContext: contextValue,
						hintsUsed: normalizedHints,
					},
				}
			} else {
				payload = {
					kind: "latex_expression",
					question,
					expected: {
						expectedLatex: expectedAnswer,
						criteria,
					},
					answer: {
						answerLatex: answerText,
					},
					context: {
						courseId,
						lessonId,
						conceptId: resolvedConceptId,
						practiceContext: contextValue,
						hintsUsed: normalizedHints,
					},
				}
			}

			setIsSubmitting(true)
			setError(null)

			try {
				const grade = await courseService.gradeLessonAnswer(lessonId, payload)
				return { grade, review: null, rating: null }
			} catch (submissionError) {
				setError(submissionError)
				logger.error("Failed to grade practice answer", submissionError, {
					courseId,
					lessonId,
					conceptId: conceptId ?? initialConceptId,
				})
				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, practiceContext, resolveConceptId, courseService, submitAttempt, initialConceptId]
	)

	const submitJxgStateAnswer = useCallback(
		async ({
			question,
			expectedState,
			answerState,
			tolerance,
			perCheckTolerance,
			criteria,
			conceptId,
			attempts,
			durationMs,
			hintsUsed,
			practiceContext: contextOverride,
		} = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for JSXGraph practice grading")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			normalizeAttempts(attempts)
			normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)
			const contextValue = contextOverride || practiceContext

			const payload = {
				kind: "jxg_state",
				question,
				expected: {
					expectedState,
					tolerance,
					perCheckTolerance,
					criteria,
				},
				answer: {
					answerState,
				},
				context: {
					courseId,
					lessonId,
					conceptId: resolvedConceptId,
					practiceContext: contextValue,
					hintsUsed: normalizedHints,
				},
			}

			setIsSubmitting(true)
			setError(null)

			try {
				const grade = await courseService.gradeLessonAnswer(lessonId, payload)
				return { grade, review: null, rating: null }
			} catch (submissionError) {
				setError(submissionError)
				logger.error("Failed to grade JSXGraph practice answer", submissionError, {
					courseId,
					lessonId,
					conceptId: conceptId ?? initialConceptId,
				})
				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, practiceContext, resolveConceptId, courseService, initialConceptId]
	)

	const submitSkip = useCallback(
		async ({ questionId, conceptId, attempts, durationMs, hintsUsed } = {}) => {
			normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)

			if (questionId) {
				setIsSubmitting(true)
				setError(null)
				try {
					return await submitAttempt({
						questionId,
						answerText: "skip",
						hintsUsed: normalizedHints,
						durationMs: normalizedDuration,
					})
				} catch (submissionError) {
					setError(submissionError)
					logger.error("Failed to submit skipped practice attempt", submissionError, {
						courseId,
						lessonId,
						conceptId: conceptId ?? initialConceptId,
						questionId,
					})
					throw submissionError
				} finally {
					setIsSubmitting(false)
				}
			}

			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for practice review")
			}

			resolveConceptId(conceptId)
			return {
				grade: {
					isCorrect: false,
					status: "unsupported",
					feedbackMarkdown: "Skipped for now.",
				},
				review: null,
				rating: null,
			}
		},
		[courseId, lessonId, resolveConceptId, submitAttempt, initialConceptId]
	)

	return useMemo(
		() => ({
			submitAnswer,
			submitJxgStateAnswer,
			submitSkip,
			isSubmitting,
			error,
		}),
		[error, isSubmitting, submitAnswer, submitJxgStateAnswer, submitSkip]
	)
}

export default useLatexPracticeReview
