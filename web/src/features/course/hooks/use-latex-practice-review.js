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

export function useLatexPracticeReview({ courseId, lessonId, conceptId: initialConceptId = null } = {}) {
	const courseService = useCourseService(courseId)

	const [isSubmitting, setIsSubmitting] = useState(false)
	const [error, setError] = useState(null)

	const submitAttempt = useCallback(
		async ({ questionId, answer, hintsUsed, durationMs }) => {
			if (!courseId) {
				throw new Error("Course ID required for practice attempt")
			}
			if (!questionId) {
				throw new Error("Question ID required for practice attempt")
			}

			const attempt = await courseService.submitAttempt({
				attemptId: crypto.randomUUID(),
				questionId,
				answer,
				hintsUsed,
				durationMs,
			})
			return { grade: attempt, attempt, rating: null, review: null }
		},
		[courseId, courseService]
	)

	const submitAnswer = useCallback(
		async ({ questionId, answerKind = "math_latex", answerText, conceptId, attempts, durationMs, hintsUsed } = {}) => {
			normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)

			if (!questionId) {
				throw new Error("Question ID required for server-owned practice attempt")
			}

			const answer =
				answerKind === "math_latex" ? { kind: "math_latex", answerLatex: answerText } : { kind: "text", answerText }

			setIsSubmitting(true)
			setError(null)

			try {
				return await submitAttempt({ questionId, answer, hintsUsed: normalizedHints, durationMs: normalizedDuration })
			} catch (submissionError) {
				setError(submissionError)
				logger.error("Failed to submit practice answer", submissionError, {
					courseId,
					lessonId,
					conceptId: conceptId ?? initialConceptId,
					questionId,
				})
				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, submitAttempt, initialConceptId]
	)

	const submitJxgStateAnswer = useCallback(
		async ({ questionId, answerState, conceptId, attempts, durationMs, hintsUsed } = {}) => {
			normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)
			if (!questionId) {
				throw new Error("Question ID required for server-owned JSXGraph attempt")
			}

			setIsSubmitting(true)
			setError(null)

			try {
				return await submitAttempt({
					questionId,
					answer: { kind: "jxg_state", answerState },
					hintsUsed: normalizedHints,
					durationMs: normalizedDuration,
				})
			} catch (submissionError) {
				setError(submissionError)
				logger.error("Failed to submit JSXGraph practice answer", submissionError, {
					courseId,
					lessonId,
					conceptId: conceptId ?? initialConceptId,
					questionId,
				})
				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, submitAttempt, initialConceptId]
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
						answer: { kind: "skip" },
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
			throw new Error("Question ID required for server-owned skip attempt")
		},
		[courseId, lessonId, submitAttempt, initialConceptId]
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
