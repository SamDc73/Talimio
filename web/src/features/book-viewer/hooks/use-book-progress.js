import { useSingleProgress, useUpdateProgress } from "@/hooks/use-progress"

/**
 * Book progress hook backed by the unified progress API
 */

export function useBookProgress(bookId) {
	const progressQuery = useSingleProgress(bookId)
	const updateProgress = useUpdateProgress()

	// Current progress and normalized metadata
	const currentProgress = progressQuery.data ?? 0
	const rawMetadata = progressQuery.metadata || {}

	// Extract values with defaults (snake_case only)
	const tocProgress = rawMetadata.toc_progress ?? {}
	const currentPage = rawMetadata.current_page ?? 0
	const totalPages = rawMetadata.total_pages ?? 0
	const tocChapterCount = Object.keys(tocProgress).length
	const totalChaptersFromMetadata =
		typeof rawMetadata.total_chapters === "number" ? rawMetadata.total_chapters : tocChapterCount
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
			const totalChapters = totalChaptersOverride ?? rawMetadata.total_chapters ?? Object.keys(newTocProgress).length
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
		updateCompletions: async (updates, totalChaptersOverride) => {
			const newTocProgress = { ...tocProgress }

			updates.forEach(({ itemId, completed }) => {
				// Backend expects boolean values
				newTocProgress[itemId] = completed
			})

			// Calculate new progress based on completed chapters
			const totalChapters = totalChaptersOverride ?? rawMetadata.total_chapters ?? Object.keys(newTocProgress).length
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
