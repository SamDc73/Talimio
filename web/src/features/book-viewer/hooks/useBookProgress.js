import { useProgress, useUpdateProgress } from "@/hooks/useProgress"

/**
 * Book progress hook backed by the unified progress API
 */

export function useBookProgress(bookId) {
	const contentIds = bookId ? [bookId] : []

	const progressQuery = useProgress(contentIds)
	const updateProgress = useUpdateProgress()

	// Current progress and normalized metadata
	const currentProgress = progressQuery.data?.[bookId] || 0
	const rawMetadata = progressQuery.metadata?.[bookId] || {}

	// Extract values with defaults (snake_case only)
	const tocProgress = rawMetadata.toc_progress || {}
	const currentPage = rawMetadata.current_page || 0
	const totalPages = rawMetadata.total_pages || 0
	const totalChaptersFromMetadata = rawMetadata.total_chapters || Object.keys(tocProgress).length
	const zoomLevel = rawMetadata.zoom_level ?? 100

	// Helper to calculate progress from TOC (only counts leaf chapters)
	const calculateProgressFromToc = (tocProgress, totalChapters) => {
		if (!totalChapters || totalChapters === 0) return 0

		// Backend expects boolean values, count only true values
		const completedCount = Object.values(tocProgress).filter((status) => status === true).length

		return Math.round((completedCount / totalChapters) * 100)
	}

	return {
		progress: {
			percentage: currentProgress,
		},
		metadata: {
			currentPage,
			totalPages,
			zoomLevel,
			tocProgress,
		},
		isLoading: progressQuery.isLoading,
		error: progressQuery.error,
		refetch: progressQuery.refetch,
		isCompleted: (chapterId) => tocProgress[chapterId] === true,
		toggleCompletion: async (chapterId, totalChaptersOverride) => {
			const currentStatus = tocProgress[chapterId] === true
			const newStatus = !currentStatus

			const newTocProgress = {
				...tocProgress,
				[chapterId]: newStatus,
			}

			// Calculate new progress based on completed chapters
			const totalChapters =
				totalChaptersOverride ??
				rawMetadata.total_chapters ??
				rawMetadata.totalChapters ??
				Object.keys(newTocProgress).length
			const newProgress = calculateProgressFromToc(newTocProgress, totalChapters)

			await updateProgress.mutateAsync({
				contentId: bookId,
				progress: newProgress,
				metadata: {
					content_type: "book",
					toc_progress: newTocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					total_chapters: totalChapters,
				},
			})
		},
		batchUpdate: async (updates, totalChaptersOverride) => {
			const newTocProgress = { ...tocProgress }

			updates.forEach(({ itemId, completed }) => {
				// Backend expects boolean values
				newTocProgress[itemId] = completed
			})

			// Calculate new progress based on completed chapters
			const totalChapters =
				totalChaptersOverride ??
				rawMetadata.total_chapters ??
				rawMetadata.totalChapters ??
				Object.keys(newTocProgress).length
			const newProgress = calculateProgressFromToc(newTocProgress, totalChapters)

			await updateProgress.mutateAsync({
				contentId: bookId,
				progress: newProgress,
				metadata: {
					content_type: "book",
					toc_progress: newTocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					total_chapters: totalChapters,
				},
			})
		},
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: bookId,
				progress,
				metadata: {
					content_type: "book",
					toc_progress: tocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					total_chapters: totalChaptersFromMetadata,
					...metadata,
				},
			}),
	}
}
