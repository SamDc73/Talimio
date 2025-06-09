const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const deleteApi = {
	async deleteVideo(id) {
		const response = await fetch(`${BASE_URL}/videos/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete video");
		}
	},

	async deleteBook(id) {
		const response = await fetch(`${BASE_URL}/books/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete book");
		}
	},

	async deleteRoadmap(id) {
		const response = await fetch(`${BASE_URL}/roadmaps/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete roadmap");
		}
	},

	async deleteFlashcardDeck(id) {
		const response = await fetch(`${BASE_URL}/flashcards/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete flashcard deck");
		}
	},

	async deleteLesson(id) {
		const response = await fetch(`${BASE_URL}/lessons/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete lesson");
		}
	},

	async deleteItem(itemType, id) {
		switch (itemType) {
			case "video":
				return this.deleteVideo(id);
			case "book":
				return this.deleteBook(id);
			case "roadmap":
				return this.deleteRoadmap(id);
			case "flashcard":
				return this.deleteFlashcardDeck(id);
			case "lesson":
				return this.deleteLesson(id);
			default:
				throw new Error(`Unknown item type: ${itemType}`);
		}
	},
};
