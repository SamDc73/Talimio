import { useRef } from "react"

import { useProgress, useUpdateProgress } from "@/hooks/useProgress"

/**
 * Adapter hook for backward compatibility with video progress
 * Maps the new unified progress API to the old video-specific interface
 */
export function useVideoProgress(videoId) {
	const contentIds = videoId ? [videoId] : []

	const progressQuery = useProgress(contentIds)
	const updateProgress = useUpdateProgress()

	// Use refs to store functions that don't need to trigger re-renders
	const refetchRef = useRef(progressQuery.refetch)
	refetchRef.current = progressQuery.refetch

	// Get the current progress data from the map
	const currentProgress = progressQuery.data?.[videoId] || 0
	const rawMetadata = progressQuery.metadata?.[videoId] || {}

	// Extract values with defaults (support both camelCase and snake_case like books)
	// Normalize completedChapters to a boolean map regardless of backend shape
	let completedChapters = {}
	if (rawMetadata.completedChapters && typeof rawMetadata.completedChapters === "object") {
		completedChapters = rawMetadata.completedChapters
	} else if (rawMetadata.completed_chapters) {
		const cc = rawMetadata.completed_chapters
		if (Array.isArray(cc)) {
			// Convert list of IDs to boolean map
			completedChapters = cc.reduce((acc, id) => {
				acc[id] = true
				return acc
			}, {})
		} else if (typeof cc === "object") {
			completedChapters = cc
		}
	}

	const totalChapters = rawMetadata.total_chapters || rawMetadata.totalChapters || 0

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
				content_type: "video",
				completed_chapters: newCompletedChapters,
				total_chapters: actualTotalChapters,
			},
		})

		// Return the new state for immediate UI update
		return !currentCompleted
	}

	// Method to set total chapters (needed for progress calculation)
	const setTotalChapters = async (newTotalChapters) => {
		await updateProgress.mutateAsync({
			contentId: videoId,
			progress: currentProgress,
			metadata: {
				content_type: "video",
				completed_chapters: completedChapters,
				total_chapters: newTotalChapters,
			},
		})
	}

	return {
		progress: {
			percentage: currentProgress,
			value: currentProgress, // Alias for compatibility
		},
		metadata: {
			completedChapters,
			totalChapters,
		},
		isLoading: progressQuery.isLoading,
		loading: progressQuery.isLoading, // Legacy alias
		error: progressQuery.error,
		refetch: () => refetchRef.current(),
		isCompleted,
		toggleCompletion,
		setTotalChapters,
		completedChapters, // Legacy direct access
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: videoId,
				progress,
				metadata: {
					content_type: "video",
					completed_chapters: completedChapters,
					total_chapters: totalChapters,
					...metadata,
				},
			}),
		// Legacy method names for compatibility
		setProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: videoId,
				progress,
				metadata: {
					content_type: "video",
					completed_chapters: completedChapters,
					total_chapters: totalChapters,
					...metadata,
				},
			}),
	}
}

/**
 * Hook for updating video-specific metadata along with progress
 */
export function useVideoProgressWithPosition(videoId) {
	const updateProgress = useUpdateProgress()
	const { progress, isLoading, error } = useVideoProgress(videoId)

	const updateVideoProgress = (position, duration) => {
		const progressPercentage = duration > 0 ? (position / duration) * 100 : 0

		updateProgress.mutate({
			contentId: videoId,
			progress: progressPercentage,
			metadata: {
				content_type: "video",
				position,
				duration,
			},
		})
	}

	return {
		progress: {
			percentage: progress.percentage,
			value: progress.percentage,
		},
		isLoading,
		error,
		updateVideoProgress,
		updatePosition: updateVideoProgress, // Use the same function
	}
}
