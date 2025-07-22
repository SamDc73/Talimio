const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const booksApi = {
	async getBook(bookId) {
		const response = await fetch(`${BASE_URL}/books/${bookId}`);

		if (!response.ok) {
			throw new Error("Failed to fetch book");
		}

		return response.json();
	},

	async updateProgress(bookId, progressData) {
		const response = await fetch(`${BASE_URL}/books/${bookId}/progress`, {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(progressData),
		});

		if (!response.ok) {
			throw new Error("Failed to update book progress");
		}

		return response.json();
	},
};
