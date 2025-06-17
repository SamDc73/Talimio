const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const deleteApi = {
	async deleteVideo(id) {
		const response = await fetch(`${BASE_URL}/content/youtube/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete video");
		}
	},

	async deleteBook(id) {
		const response = await fetch(`${BASE_URL}/content/book/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete book");
		}
	},

	async deleteRoadmap(id) {
		const response = await fetch(`${BASE_URL}/content/roadmap/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete roadmap");
		}
	},

	async deleteFlashcardDeck(id) {
		const response = await fetch(`${BASE_URL}/content/flashcards/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete flashcard deck");
		}
	},

	async deleteLesson(id) {
		const response = await fetch(`${BASE_URL}/content/course/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			throw new Error("Failed to delete lesson");
		}
	},

	async deleteItem(itemType, id) {
		// Map frontend item types to backend content types
		const contentTypeMap = {
			video: "youtube",
			book: "book",
			roadmap: "roadmap",
			flashcard: "flashcards",
			lesson: "course",
			course: "course",
			youtube: "youtube",
			flashcards: "flashcards",
		};

		const contentType = contentTypeMap[itemType] || itemType;

		const response = await fetch(`${BASE_URL}/content/${contentType}/${id}`, {
			method: "DELETE",
		});

		if (!response.ok) {
			const errorMsg = `Failed to delete ${itemType}`;
			throw new Error(errorMsg);
		}
	},
};
