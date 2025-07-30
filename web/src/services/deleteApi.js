import { api } from "@/lib/apiClient";

export const deleteApi = {
	async deleteVideo(id) {
		return this.deleteItem("youtube", id);
	},

	async deleteBook(id) {
		return this.deleteItem("book", id);
	},

	async deleteCourse(id) {
		return this.deleteItem("course", id);
	},

	async deleteFlashcardDeck(id) {
		return this.deleteItem("flashcards", id);
	},

	async deleteItem(itemType, id) {
		// Map web app item types to backend content types
		const contentTypeMap = {
			video: "youtube",
			youtube: "youtube",
			book: "book",
			flashcard: "flashcards",
			flashcards: "flashcards",
			course: "course",
			roadmap: "course",
		};

		const contentType = contentTypeMap[itemType] || itemType;

		console.log(
			`🔍 deleteItem called with itemType: "${itemType}", mapped to: "${contentType}"`,
		);
		console.log(`📞 Will call: DELETE /api/v1/content/${contentType}/${id}`);

		try {
			const response = await api.delete(`/content/${contentType}/${id}`);
			// DELETE endpoints typically return 204 No Content, which is a success
			return response;
		} catch (error) {
			console.error(`Failed to delete ${itemType}:`, error);
			const errorMsg =
				error.response?.data?.detail || `Failed to delete ${itemType}`;
			throw new Error(errorMsg);
		}
	},
};
