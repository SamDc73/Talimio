import { useApi } from "@/hooks/use-api"

/**
 * Hook for book chapter operations
 * @param {string} bookId - The book ID
 */
export function useBookChaptersApi(bookId = null) {
	const getChapters = useApi("/books/{bookId}/chapters")
	const getChapter = useApi("/books/{bookId}/chapters/{chapterId}")
	const updateChapterStatus = useApi("/books/{bookId}/chapters/{chapterId}/status", { method: "PUT" })
	const extractChapters = useApi("/books/{bookId}/extract-chapters", {
		method: "POST",
	})

	return {
		// Get all chapters for a book
		async fetchChapters() {
			if (!bookId) throw new Error("Book ID required")
			return await getChapters.execute(null, { pathParams: { bookId } })
		},

		// Get a specific chapter
		async fetchChapter(chapterId) {
			if (!bookId || !chapterId) throw new Error("Book ID and Chapter ID required")
			return await getChapter.execute(null, {
				pathParams: { bookId, chapterId },
			})
		},

		// Update chapter status
		async updateChapterStatus(chapterId, status) {
			if (!bookId || !chapterId) throw new Error("Book ID and Chapter ID required")
			return await updateChapterStatus.execute({ status }, { pathParams: { bookId, chapterId } })
		},

		// Extract chapters from book
		async extractChapters() {
			if (!bookId) throw new Error("Book ID required")
			return await extractChapters.execute(null, { pathParams: { bookId } })
		},

		// Loading states
		isLoading:
			getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
		error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
		data: getChapters.data,
	}
}
