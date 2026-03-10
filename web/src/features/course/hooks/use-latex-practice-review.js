import { useCallback, useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import logger from "@/lib/logger"
import { useCourseProgress } from "./use-course-progress"
import { useLectorReview } from "./use-lector-review"

const LOW_FRICTION_MAX_ATTEMPTS = 1
const LOW_FRICTION_MAX_MS = 30_000
const MEDIUM_FRICTION_MAX_ATTEMPTS = 2
const MEDIUM_FRICTION_MAX_MS = 90_000

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

const deriveRating = ({ isCorrect, attempts, durationMs, skipped, hintsUsed }) => {
	if (!isCorrect || skipped) {
		return 1
	}
	const usedHints = hintsUsed > 0
	if (attempts <= LOW_FRICTION_MAX_ATTEMPTS && durationMs <= LOW_FRICTION_MAX_MS) {
		return usedHints ? 3 : 4
	}
	if (attempts <= MEDIUM_FRICTION_MAX_ATTEMPTS && durationMs <= MEDIUM_FRICTION_MAX_MS) {
		return usedHints ? 2 : 3
	}
	return 2
}

export function useLatexPracticeReview({
	courseId,
	lessonId,
	conceptId: initialConceptId = null,
	practiceContext = "inline",
	onSuccess,
	onError,
} = {}) {
	const courseService = useCourseService(courseId)
	const { progress, updateProgressAsync } = useCourseProgress(courseId)
	const progressPercentage = typeof progress?.percentage === "number" ? progress.percentage : 0
	const { submitReview } = useLectorReview({
		courseId,
		lessonId,
		conceptId: initialConceptId,
		onSuccess,
		onError,
	})

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

	const persistPracticeMetadata = useCallback(
		async ({ conceptId, rating, attempts, durationMs, hintsUsed, context }) => {
			if (!courseId || typeof updateProgressAsync !== "function") {
				return
			}

			try {
				await updateProgressAsync(progressPercentage, {
					practice_state_update: {
						last_practice_at: new Date().toISOString(),
						last_practice_context: context,
						last_practice_concept: String(conceptId),
						last_practice_rating: rating,
						last_practice_attempts: attempts,
						last_practice_duration_ms: durationMs,
						last_practice_hints_used: hintsUsed,
					},
				})
			} catch (metadataError) {
				logger.error("Failed to persist practice metadata", metadataError, {
					courseId,
					lessonId,
					conceptId,
				})
			}
		},
		[courseId, lessonId, progressPercentage, updateProgressAsync]
	)

	const submitAnswer = useCallback(
		async ({
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
			reviewMetadata,
		} = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for practice grading")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			const normalizedAttempts = normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)
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
				let review = null
				let rating = null

				if (grade) {
					rating = deriveRating({
						isCorrect: grade.isCorrect,
						attempts: normalizedAttempts,
						durationMs: normalizedDuration,
						skipped: false,
						hintsUsed: normalizedHints,
					})
					review = await submitReview({
						conceptId: resolvedConceptId,
						rating,
						reviewDurationMs: normalizedDuration,
						reviewMetadata,
					})

					await persistPracticeMetadata({
						conceptId: resolvedConceptId,
						rating,
						attempts: normalizedAttempts,
						durationMs: normalizedDuration,
						context: contextValue,
						hintsUsed: normalizedHints,
					})
				}

				return { grade, review, rating }
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
		[
			courseId,
			lessonId,
			practiceContext,
			resolveConceptId,
			courseService,
			submitReview,
			persistPracticeMetadata,
			initialConceptId,
		]
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
			reviewMetadata,
		} = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for JSXGraph practice grading")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			const normalizedAttempts = normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
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
				let review = null
				let rating = null

				if (grade) {
					rating = deriveRating({
						isCorrect: grade.isCorrect,
						attempts: normalizedAttempts,
						durationMs: normalizedDuration,
						skipped: false,
						hintsUsed: normalizedHints,
					})
					review = await submitReview({
						conceptId: resolvedConceptId,
						rating,
						reviewDurationMs: normalizedDuration,
						reviewMetadata,
					})

					await persistPracticeMetadata({
						conceptId: resolvedConceptId,
						rating,
						attempts: normalizedAttempts,
						durationMs: normalizedDuration,
						context: contextValue,
						hintsUsed: normalizedHints,
					})
				}

				return { grade, review, rating }
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
		[
			courseId,
			lessonId,
			practiceContext,
			resolveConceptId,
			courseService,
			submitReview,
			persistPracticeMetadata,
			initialConceptId,
		]
	)

	const submitSkip = useCallback(
		async ({ conceptId, attempts, durationMs, hintsUsed, practiceContext: contextOverride, reviewMetadata } = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for practice review")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			const normalizedAttempts = normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)
			const contextValue = contextOverride || practiceContext

			setIsSubmitting(true)
			setError(null)

			try {
				const rating = deriveRating({
					isCorrect: false,
					attempts: normalizedAttempts,
					durationMs: normalizedDuration,
					skipped: true,
					hintsUsed: normalizedHints,
				})
				const review = await submitReview({
					conceptId: resolvedConceptId,
					rating,
					reviewDurationMs: normalizedDuration,
					reviewMetadata,
				})

				await persistPracticeMetadata({
					conceptId: resolvedConceptId,
					rating,
					attempts: normalizedAttempts,
					durationMs: normalizedDuration,
					context: contextValue,
					hintsUsed: normalizedHints,
				})

				return { review, rating }
			} catch (submissionError) {
				setError(submissionError)
				logger.error("Failed to submit skipped practice review", submissionError, {
					courseId,
					lessonId,
					conceptId: conceptId ?? initialConceptId,
				})
				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, practiceContext, resolveConceptId, submitReview, persistPracticeMetadata, initialConceptId]
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
