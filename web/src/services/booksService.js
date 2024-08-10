/**
 * Service for managing book chapters and their progress
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1"

/**
 * Fetch chapters for a book
 * @param {string} bookId - The ID of the book
 * @returns {Promise<Array>} Array of chapters
 */
export async function getBookChapters(bookId) {
	const headers = {}

	// Add Supabase auth token if available
	if (import.meta.env.VITE_ENABLE_AUTH === "true") {
		const { supabase } = await import("../lib/supabase")
		const {
			data: { session },
		} = await supabase.auth.getSession()
		if (session?.access_token) {
			headers.Authorization = `Bearer ${session.access_token}`
		}
	}

	const response = await fetch(`${API_BASE}/books/${bookId}/chapters`, {
		headers,
		credentials: import.meta.env.VITE_ENABLE_AUTH === "false" ? "omit" : "include",
	})
	if (!response.ok) {
		throw new Error(`Failed to fetch book chapters: ${response.statusText}`)
	}
	return await response.json()
}

/**
 * Get a specific chapter
 * @param {string} bookId - The ID of the book
 * @param {string} chapterId - The ID of the chapter
 * @returns {Promise<Object>} Chapter data
 */
export async function getBookChapter(bookId, chapterId) {
	const response = await fetch(`${API_BASE}/books/${bookId}/chapters/${chapterId}`)
	if (!response.ok) {
		throw new Error(`Failed to fetch chapter: ${response.statusText}`)
	}
	return await response.json()
}

/**
 * Update chapter status
 * @param {string} bookId - The ID of the book
 * @param {string} chapterId - The ID of the chapter
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} Update response
 */
export async function updateChapterStatus(bookId, chapterId, status) {
	const response = await fetch(`${API_BASE}/books/${bookId}/chapters/${chapterId}/status`, {
		method: "PUT",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ status }),
	})

	if (!response.ok) {
		throw new Error(`Failed to update chapter status: ${response.statusText}`)
	}
	return await response.json()
}

/**
 * Extract chapters from book
 * @param {string} bookId - The ID of the book
 * @returns {Promise<Object>} Extraction response
 */
export async function extractBookChapters(bookId) {
	const response = await fetch(`${API_BASE}/books/${bookId}/extract-chapters`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
	})

	if (!response.ok) {
		throw new Error(`Failed to extract chapters: ${response.statusText}`)
	}
	return await response.json()
}
