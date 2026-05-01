import { useCallback } from "react"
import { useSingleProgress, useUpdateProgress } from "@/hooks/use-progress"

/**
 * Video progress hook backed by the unified progress API
 */
export function useVideoProgress(videoId) {
	const progressQuery = useSingleProgress(videoId)
	const updateProgress = useUpdateProgress()

	// Current progress and normalized metadata
	const currentProgress = progressQuery.data ?? 0
	const rawMetadata = progressQuery.metadata || {}

	// Extract values with defaults (snake_case only)
	const completedChapters = (typeof rawMetadata.completed_chapters === "object" && rawMetadata.completed_chapters) || {}
	const totalChapters = rawMetadata.total_chapters ?? 0

	// Check if a specific chapter is completed
	const isCompleted = (chapterId) => {
		return completedChapters[chapterId] === true
	}

	// Toggle chapter completion
	const toggleCompletion = async (chapterId, totalChaptersOverride) => {
		const currentCompleted = completedChapters[chapterId] || false
		const newCompletedChapters = {
			...completedChapters,
			[chapterId]: !currentCompleted,
		}

		// Use override if provided (from VideoSidebar which knows the actual chapter count)
		const actualTotalChapters = totalChaptersOverride ?? totalChapters ?? Object.keys(newCompletedChapters).length

		// Calculate progress based on completed chapters
		let newProgress = currentProgress
		if (actualTotalChapters && actualTotalChapters > 0) {
			const completedCount = Object.values(newCompletedChapters).filter(Boolean).length
			newProgress = Math.round((completedCount / actualTotalChapters) * 100)
		}

		// Update both progress and metadata (only send necessary fields)
		await updateProgress.mutateAsync({
			contentId: videoId,
			progress: newProgress,
			metadata: {
				...rawMetadata,
				content_type: "video",
				completed_chapters: newCompletedChapters,
				total_chapters: actualTotalChapters,
			},
		})
	}

	return {
		progress: {
			percentage: currentProgress,
		},
		metadata: {
			completedChapters,
			totalChapters,
		},
		rawMetadata,
		isLoading: progressQuery.isLoading,
		error: progressQuery.error,
		refetch: progressQuery.refetch,
		isCompleted,
		toggleCompletion,
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: videoId,
				progress,
				metadata: {
					...rawMetadata,
					content_type: "video",
					completed_chapters: completedChapters,
					total_chapters: totalChapters,
					...metadata,
				},
			}),
	}
}

/**
 * Hook for updating video-specific time-based progress metadata
 */
export function useVideoProgressWithPosition(videoId) {
	const updateProgress = useUpdateProgress()
	const { progress, isLoading, error, rawMetadata } = useVideoProgress(videoId)
	const savedPosition = rawMetadata.position ?? rawMetadata.last_position ?? 0

	const updatePlaybackProgress = useCallback(
		(position, duration) => {
			const progressPercentage = duration > 0 ? (position / duration) * 100 : 0

			updateProgress.mutate({
				contentId: videoId,
				progress: progressPercentage,
				metadata: {
					...rawMetadata,
					content_type: "video",
					position,
					duration,
				},
			})
		},
		[rawMetadata, updateProgress, videoId]
	)

	return {
		progress: {
			percentage: progress.percentage,
		},
		isLoading,
		error,
		rawMetadata,
		savedPosition,
		updatePlaybackProgress,
	}
}
