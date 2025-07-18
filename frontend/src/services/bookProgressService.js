const API_BASE = "/api/v1";
const REQUEST_TIMEOUT = 7000;

async function fetchWithTimeout(url, options = {}) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
		});
		clearTimeout(timeout);
		return response;
	} catch (error) {
		clearTimeout(timeout);
		if (error.name === "AbortError") {
			throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`);
		}
		throw error;
	}
}

export async function updateBookChapterStatus(bookId, chapterId, status) {
	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/books/${bookId}/chapters/${chapterId}/status`,
			{
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			},
		);

		if (!response.ok) {
			throw new Error(
				`Failed to update chapter status: ${response.statusText}`,
			);
		}
		const data = await response.json();
		return data;
	} catch (error) {
		console.error("Error updating chapter status:", error);
		throw error;
	}
}
