import { useCallback, useMemo, useState } from "react"
import logger from "@/lib/logger"
import { useCourseService } from "../api/courseApi.js"
import { useCourseProgress } from "./useCourseProgress.js"
import { useLectorReview } from "./useLectorReview.js"

const LOW_FRICTION_MAX_ATTEMPTS = 1
const LOW_FRICTION_MAX_MS = 30_000
const MEDIUM_FRICTION_MAX_ATTEMPTS = 2
const MEDIUM_FRICTION_MAX_MS = 90_000

const normalizeAttempts = (attempts) => {
	if (typeof attempts !== "number" || Number.isNaN(attempts) || attempts <= 0) {
		return 1
	}
	return Math.round(attempts)
}

const normalizeDuration = (durationMs) => {
	if (typeof durationMs !== "number" || Number.isNaN(durationMs) || durationMs <= 0) {
		return 0
	}
	return Math.round(durationMs)
}

const normalizeHintsUsed = (hintsUsed) => {
	if (typeof hintsUsed !== "number" || Number.isNaN(hintsUsed) || hintsUsed < 0) {
		return 0
	}
	return Math.round(hintsUsed)
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
				throw new Error("Concept ID required for LaTeX practice review submission")
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
				logger.error("Failed to persist LaTeX practice metadata", metadataError, {
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
			expectedLatex,
			criteria,
			answerLatex,
			conceptId,
			attempts,
			durationMs,
			hintsUsed,
			practiceContext: contextOverride,
		} = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for LaTeX practice grading")
			}

			const resolvedConceptId = resolveConceptId(conceptId)
			const normalizedAttempts = normalizeAttempts(attempts)
			const normalizedDuration = normalizeDuration(durationMs)
			const normalizedHints = normalizeHintsUsed(hintsUsed)
			const contextValue = contextOverride || practiceContext

			const payload = {
				kind: "latex_expression",
				question,
				expected: {
					expectedLatex,
					criteria,
				},
				answer: {
					answerLatex,
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
				logger.error("Failed to grade LaTeX practice answer", submissionError, {
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
		async ({ conceptId, attempts, durationMs, hintsUsed, practiceContext: contextOverride } = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for LaTeX practice review")
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
				logger.error("Failed to submit skipped LaTeX practice review", submissionError, {
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
			submitSkip,
			isSubmitting,
			error,
		}),
		[error, isSubmitting, submitAnswer, submitSkip]
	)
}

export default useLatexPracticeReview
