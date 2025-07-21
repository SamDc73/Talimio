import api from "./api";

export const deleteApi = {
	async deleteVideo(id) {
		return this.deleteItem("youtube", id);
	},

	async deleteBook(id) {
		return this.deleteItem("book", id);
	},

	async deleteRoadmap(id) {
		return this.deleteItem("roadmap", id);
	},

	async deleteFlashcardDeck(id) {
		return this.deleteItem("flashcards", id);
	},

	async deleteLesson(id) {
		return this.deleteItem("roadmap", id);
	},

	async deleteItem(itemType, id) {
		// Map frontend item types to backend content types
		const contentTypeMap = {
			video: "youtube",
			youtube: "youtube",
			book: "book",
			roadmap: "roadmap",
			flashcard: "flashcards",
			flashcards: "flashcards",
			course: "roadmap",
		};

		const contentType = contentTypeMap[itemType] || itemType;

		try {
			const response = await api.delete(`/content/${contentType}/${id}`);
			// DELETE endpoints typically return 204 No Content, which is a success
			return response;
		} catch (error) {
			console.error(`Failed to delete ${itemType}:`, error);
			const errorMsg = error.response?.data?.detail || `Failed to delete ${itemType}`;
			throw new Error(errorMsg);
		}
	},
};
