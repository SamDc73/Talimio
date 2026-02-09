import { useCallback, useMemo } from "react"
import { useProgress, useUpdateProgress } from "@/hooks/use-progress"

/**
 * Course progress hook backed by the unified progress API
 */

export function useCourseProgress(courseId) {
	const contentIds = courseId ? [courseId] : []

	const progressQuery = useProgress(contentIds)
	const updateProgress = useUpdateProgress()

	// Current progress and normalized metadata
	const currentProgress = progressQuery.data?.[courseId] || 0
	const rawMetadata = progressQuery.metadata?.[courseId] || {}

	// Extract values with defaults
	let completedLessonsArray = rawMetadata.completed_lessons
	if (!Array.isArray(completedLessonsArray)) {
		completedLessonsArray = []
	}
	const currentLessonId = rawMetadata.current_lesson_id
	const totalLessons = rawMetadata.total_lessons || 0

	// Helper to calculate progress from completed lessons
	const calculateProgressFromLessons = (completedLessons, totalLessons) => {
		if (!totalLessons || totalLessons === 0) return 0
		return Math.round((completedLessons.length / totalLessons) * 100)
	}

	const baseMetadata = useMemo(
		() => ({
			content_type: "course",
			completed_lessons: completedLessonsArray,
			current_lesson_id: currentLessonId,
			total_lessons: totalLessons,
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
				completed_lessons: newCompletedLessons,
				current_lesson_id: lessonIdStr,
				total_lessons: actualTotalLessons,
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
