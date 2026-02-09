import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import logger from "@/lib/logger"
import { useCourseProgress } from "./use-course-progress"

const normalizeConcept = (concept) => {
	if (!concept || typeof concept !== "object") {
		return null
	}

	const conceptId = concept.id ?? concept.conceptId ?? concept.concept_id ?? null
	if (!conceptId) {
		return null
	}

	const lessonId =
		concept.lessonId ?? concept.lesson_id ?? concept.lessonIdRef ?? concept.lesson_id_ref ?? concept.lesson?.id ?? null

	return {
		conceptId: String(conceptId),
		lessonId: lessonId ? String(lessonId) : null,
		title: concept.name || concept.title || null,
		description: concept.description || null,
		mastery: typeof concept.mastery === "number" ? concept.mastery : null,
		nextReviewAt: concept.nextReviewAt ?? concept.next_review_at ?? null,
	}
}

export function useAdaptiveSession(courseId, lessonId) {
	const courseService = useCourseService(courseId)
	const courseProgress = useCourseProgress(courseId)
	const { progress: progressSnapshot, rawMetadata = {}, refetch } = courseProgress
	const updateProgressAsync = courseProgress.updateProgressAsync
	const progressPercentage = progressSnapshot?.percentage ?? 0

	const queryClient = useQueryClient()
	const [reviewSummary, setReviewSummary] = useState(null)

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId),
		staleTime: 30_000,
		refetchOnWindowFocus: false,
	})

	const queue = useMemo(() => {
		if (!frontierData || !Array.isArray(frontierData?.dueForReview)) {
			return []
		}
		return frontierData.dueForReview.map((concept) => normalizeConcept(concept)).filter(Boolean)
	}, [frontierData])

	const fallbackConcept = useMemo(() => {
		const source = Array.isArray(frontierData?.frontier) ? frontierData.frontier[0] : null
		return source ? normalizeConcept(source) : null
	}, [frontierData])

	const nextConcept = queue[0] ?? fallbackConcept ?? null

	const isAdaptiveEnabled = useMemo(() => {
		if (typeof rawMetadata.adaptive_enabled === "boolean") return rawMetadata.adaptive_enabled
		if (typeof rawMetadata.adaptiveEnabled === "boolean") return rawMetadata.adaptiveEnabled
		return Boolean(queue.length > 0 || frontierData)
	}, [frontierData, queue.length, rawMetadata])

	const persistAdaptiveMetadata = useCallback(
		async (metadataPatch = {}, options = {}) => {
			if (!courseId) {
				throw new Error("courseId is required to persist adaptive metadata")
			}
			if (typeof updateProgressAsync !== "function") {
				throw new TypeError("updateProgressAsync is unavailable")
			}

			const nextProgress = typeof options.progress === "number" ? options.progress : progressPercentage
			return await updateProgressAsync(nextProgress, metadataPatch)
		},
		[courseId, progressPercentage, updateProgressAsync]
	)

	const handleReviewSuccess = useCallback(
		async (response, _reviews) => {
			const outcomes = Array.isArray(response?.outcomes) ? response.outcomes : []
			setReviewSummary({
				outcomes,
				recordedAt: new Date().toISOString(),
			})

			try {
				await refetch()
				await queryClient.invalidateQueries({ queryKey: ["course", courseId, "adaptive-concepts"], exact: true })
			} catch (refetchError) {
				logger.error("Failed to refresh adaptive progress after review", refetchError, {
					courseId,
					lessonId,
				})
			}
		},
		[courseId, lessonId, queryClient, refetch]
	)

	const handleReviewError = useCallback(
		(submissionError, reviews) => {
			logger.error("Adaptive review submission failed", submissionError, {
				courseId,
				lessonId,
				reviewCount: Array.isArray(reviews) ? reviews.length : 0,
			})
		},
		[courseId, lessonId]
	)

	const clearReviewSummary = useCallback(() => {
		setReviewSummary(null)
	}, [])

	const adaptiveSnapshot = useMemo(
		() => ({
			enabled: isAdaptiveEnabled,
			queue,
			nextConcept,
			dueCount: queue.length,
			avgMastery: typeof frontierData?.avgMastery === "number" ? frontierData.avgMastery : null,
			raw: frontierData,
			reviewSummary,
		}),
		[frontierData, isAdaptiveEnabled, nextConcept, queue, reviewSummary]
	)

	return {
		...courseProgress,
		adaptive: adaptiveSnapshot,
		onReviewSuccess: handleReviewSuccess,
		onReviewError: handleReviewError,
		clearReviewSummary,
		persistAdaptiveMetadata,
	}
}

export default useAdaptiveSession
