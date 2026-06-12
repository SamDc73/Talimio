import { useCallback, useMemo } from "react"
import { useSingleProgress, useUpdateProgress } from "@/hooks/use-progress"

/**
 * Course progress hook backed by the unified progress API
 */

export function useCourseProgress(courseId) {
	const progressQuery = useSingleProgress(courseId)
	const updateProgress = useUpdateProgress()

	// Current progress and normalized metadata
	const currentProgress = progressQuery.data ?? 0
	const rawMetadata = progressQuery.metadata || {}

	// Extract values with defaults
	let completedLessonsArray = rawMetadata.completedLessons
	if (!Array.isArray(completedLessonsArray)) {
		completedLessonsArray = []
	}
	const currentLessonId = rawMetadata.currentLessonId
	const totalLessons = rawMetadata.totalLessons ?? 0

	// Helper to calculate progress from completed lessons
	const calculateProgressFromLessons = (completedLessons, totalLessons) => {
		if (!totalLessons || totalLessons === 0) return 0
		return Math.round((completedLessons.length / totalLessons) * 100)
	}

	const baseMetadata = useMemo(
		() => ({
			contentType: "course",
			completedLessons: completedLessonsArray,
			currentLessonId,
			totalLessons,
		}),
		[completedLessonsArray, currentLessonId, totalLessons]
	)

	const buildMetadataPayload = useCallback(
		(extra = {}) => ({
			...rawMetadata,
			...baseMetadata,
			...extra,
		}),
		[baseMetadata, rawMetadata]
	)

	// Check if a specific lesson is completed
	const isCompleted = (lessonId) => {
		return completedLessonsArray.includes(String(lessonId))
	}

	// Toggle lesson completion
	const toggleCompletion = async (lessonId, totalLessonsOverride) => {
		const lessonIdStr = String(lessonId)
		let newCompletedLessons

		if (completedLessonsArray.includes(lessonIdStr)) {
			// Remove from completed
			newCompletedLessons = completedLessonsArray.filter((id) => id !== lessonIdStr)
		} else {
			// Add to completed
			newCompletedLessons = [...completedLessonsArray, lessonIdStr]
		}

		// Determine total lessons with override fallback (match videos/books pattern)
		const actualTotalLessons =
			totalLessonsOverride ??
			(typeof totalLessons === "number" && totalLessons > 0 ? totalLessons : newCompletedLessons.length)

		// Calculate new progress based on completed lessons
		const newProgress = calculateProgressFromLessons(newCompletedLessons, actualTotalLessons)

		await updateProgress.mutateAsync({
			contentId: courseId,
			progress: newProgress,
			metadata: buildMetadataPayload({
				completedLessons: newCompletedLessons,
				currentLessonId: lessonIdStr,
				totalLessons: actualTotalLessons,
			}),
		})
	}

	const updateProgressAsync = useCallback(
		async (progress, metadata = {}) => {
			await updateProgress.mutateAsync({
				contentId: courseId,
				progress,
				metadata: buildMetadataPayload(metadata),
			})
		},
		[buildMetadataPayload, courseId, updateProgress]
	)

	return {
		progress: {
			percentage: currentProgress,
		},
		metadata: {
			completedLessons: completedLessonsArray,
			currentLessonId,
			totalLessons,
		},
		rawMetadata,
		isLoading: progressQuery.isLoading,
		error: progressQuery.error,
		refetch: progressQuery.refetch,
		isCompleted,
		toggleCompletion,
		updateProgressAsync,
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: courseId,
				progress,
				metadata: buildMetadataPayload(metadata),
			}),
	}
}
