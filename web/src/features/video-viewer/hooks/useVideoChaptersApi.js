import { useApi } from "@/hooks/useApi"

/**
 * Hook for video chapter operations
 * @param {string} videoId - The video ID
 */
export function useVideoChaptersApi(videoId = null) {
	const getChapters = useApi("/videos/{videoId}/chapters")
	const getChapter = useApi("/videos/{videoId}/chapters/{chapterId}")
	const updateChapterStatus = useApi("/videos/{videoId}/chapters/{chapterId}/status", { method: "PUT" })
	const extractChapters = useApi("/videos/{videoId}/extract-chapters", {
		method: "POST",
	})

	return {
		// Get all chapters for a video
		async fetchChapters() {
			if (!videoId) throw new Error("Video ID required")
			return await getChapters.execute(null, { pathParams: { videoId } })
		},

		// Get a specific chapter
		async fetchChapter(chapterId) {
			if (!videoId || !chapterId) throw new Error("Video ID and Chapter ID required")
			return await getChapter.execute(null, {
				pathParams: { videoId, chapterId },
			})
		},

		// Update chapter status
		async updateChapterStatus(chapterId, status) {
			if (!videoId || !chapterId) throw new Error("Video ID and Chapter ID required")
			return await updateChapterStatus.execute({ status }, { pathParams: { videoId, chapterId } })
		},

		// Extract chapters from video
		async extractChapters() {
			if (!videoId) throw new Error("Video ID required")
			return await extractChapters.execute(null, { pathParams: { videoId } })
		},

		// Loading states
		isLoading:
			getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
		error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
		data: getChapters.data,
	}
}
