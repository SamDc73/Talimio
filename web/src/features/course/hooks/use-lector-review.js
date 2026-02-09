import { useCallback, useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import logger from "@/lib/logger"

function clampRating(value) {
	if (typeof value !== "number" || Number.isNaN(value)) {
		return null
	}
	return Math.min(Math.max(Math.round(value), 1), 4)
}

/**
 * Minimal adaptive review submission (no latency/timers).
 */
export function useLectorReview({ courseId, lessonId, conceptId: initialConceptId = null, onSuccess, onError } = {}) {
	const courseService = useCourseService(courseId)
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [error, setError] = useState(null)

	const ensureConceptId = useCallback(
		(targetConceptId) => {
			const concept = targetConceptId ?? initialConceptId
			if (!concept) {
				throw new Error("Concept ID required for adaptive review submission")
			}
			return concept
		},
		[initialConceptId]
	)

	const submitReview = useCallback(
		async ({ conceptId: targetConceptId, rating, reviewDurationMs } = {}) => {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required for adaptive review submission")
			}

			const concept = ensureConceptId(targetConceptId)
			const normalizedRating = clampRating(rating)
			if (!normalizedRating) {
				throw new Error("Rating must be a number between 1 and 4")
			}

			// Backend requires reviewDurationMs (>0); fall back to 1000ms if missing
			const duration =
				typeof reviewDurationMs === "number" && reviewDurationMs > 0 ? Math.round(reviewDurationMs) : 1000

			const payload = [
				{
					conceptId: concept,
					rating: normalizedRating,
					reviewDurationMs: duration,
				},
			]

			setIsSubmitting(true)
			setError(null)

			try {
				const response = await courseService.submitLessonReviews(lessonId, payload)

				if (typeof onSuccess === "function") {
					onSuccess(response, payload)
				}

				const primaryOutcome = Array.isArray(response?.outcomes) ? response.outcomes[0] : null

				logger.info("Adaptive review submitted", {
					courseId,
					lessonId,
					conceptId: concept,
					rating: normalizedRating,
					reviewDurationMs: duration,
					nextReviewAt: primaryOutcome?.nextReviewAt ?? primaryOutcome?.next_review_at ?? null,
					mastery: primaryOutcome?.mastery ?? null,
					exposures: primaryOutcome?.exposures ?? null,
				})

				return response
			} catch (submissionError) {
				setError(submissionError)

				if (typeof onError === "function") {
					onError(submissionError, payload)
				}

				logger.error("Failed to submit adaptive review", submissionError, {
					courseId,
					lessonId,
					conceptId: targetConceptId ?? initialConceptId,
				})

				throw submissionError
			} finally {
				setIsSubmitting(false)
			}
		},
		[courseId, lessonId, ensureConceptId, courseService, onSuccess, onError, initialConceptId]
	)

	return useMemo(
		() => ({
			submitReview,
			isSubmitting,
			error,
		}),
		[error, isSubmitting, submitReview]
	)
}

export default useLectorReview
