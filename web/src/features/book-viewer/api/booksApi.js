import { api } from "@/lib/apiClient"

export const booksApi = {
	async getBook(bookId) {
		return api.get(`/books/${bookId}`)
	},

	async updateProgress(bookId, progressData) {
		return api.put(`/books/${bookId}/progress`, progressData)
	},
}
