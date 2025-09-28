const API_BASE = "/api/v1"
const REQUEST_TIMEOUT = 7000

async function fetchWithTimeout(url, options = {}) {
	const controller = new AbortController()
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)

	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
			credentials: "include", // Include cookies for authentication
		})
		clearTimeout(timeout)
		return response
	} catch (error) {
		clearTimeout(timeout)
		if (error.name === "AbortError") {
			throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`)
		}
		throw error
	}
}

export async function updateBookChapterStatus(bookId, chapterId, status) {
	// Check if this is a ToC ID (like "toc_1_1_6") or a UUID
	const isTocId = chapterId.startsWith("toc_")

	if (isTocId) {
		// For ToC IDs, use the progress endpoint
		const requestBody = {
			tocProgress: {
				[chapterId]: status === "completed",
			},
		}

		const response = await fetchWithTimeout(`${API_BASE}/books/${bookId}/progress`, {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(requestBody),
		})

		if (!response.ok) {
			throw new Error(`Failed to update ToC progress: ${response.statusText}`)
		}
		const data = await response.json()
		return data
	}
	// For UUID chapters, use the chapters endpoint
	const response = await fetchWithTimeout(`${API_BASE}/books/${bookId}/chapters/${chapterId}/status`, {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ status }),
	})

	if (!response.ok) {
		throw new Error(`Failed to update chapter status: ${response.statusText}`)
	}
	const data = await response.json()
	return data
}
