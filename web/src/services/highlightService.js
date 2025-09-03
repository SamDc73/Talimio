/**
 * Service layer for highlight API calls.
 * Handles all HTTP communication with the backend highlight endpoints.
 */

import { api } from "@/lib/apiClient"

export const highlightService = {
	/**
	 * Get all highlights for a content item
	 */
	async getHighlights(contentType, contentId) {
		try {
			// Support highlights for 'book', 'pdf' (PDFs are stored under the parent book), and 'video'
			if (contentType !== "book" && contentType !== "pdf" && contentType !== "video") {
				return []
			}

			// Map content type to the correct API endpoint
			const endpoint = this.getEndpoint(contentType, contentId)
			const response = await api.get(`${endpoint}/highlights`)
			const list = response || []
			return list
		} catch (error) {
			// Only log non-auth errors
			if (error?.status !== 401 && error?.status !== 422) {
			}
			throw error // Allow apiClient to handle auth refresh
		}
	},

	/**
	 * Create a new highlight
	 */
	async createHighlight(contentType, contentId, highlightData) {
		// Support creating highlights for 'book', 'pdf' (PDFs are stored under the parent book), and 'video'
		if (contentType !== "book" && contentType !== "pdf" && contentType !== "video") {
			return null
		}

		const endpoint = this.getEndpoint(contentType, contentId)
		const body = { source_data: highlightData }
		const response = await api.post(`${endpoint}/highlights`, body)
		return response
	},

	/**
	 * Delete a highlight
	 */
	async deleteHighlight(highlightId, contentType = null) {
		// If we know the content type, use the correct endpoint directly
		if (contentType === "book" || contentType === "pdf") {
			const response = await api.delete(`/books/highlights/${highlightId}`)
			return response
		}

		if (contentType === "video") {
			const response = await api.delete(`/videos/highlights/${highlightId}`)
			return response
		}

		// If content type is unknown, try both endpoints intelligently
		// Try video endpoint first (newer implementation), then book endpoint
		const endpoints = [
			{ name: "video", url: `/videos/highlights/${highlightId}` },
			{ name: "book", url: `/books/highlights/${highlightId}` },
		]

		let lastError = null

		for (const endpoint of endpoints) {
			try {
				const response = await api.delete(endpoint.url)
				return response
			} catch (error) {
				lastError = error
				if (error.status === 404) {
				} else {
					throw error
				}
			}
		}
		throw lastError || new Error("Highlight not found")
	},

	/**
	 * Update a highlight (future use)
	 */
	async updateHighlight(highlightId, data, contentType = null) {
		// If we know the content type, use the correct endpoint directly
		if (contentType === "book" || contentType === "pdf") {
			const response = await api.put(`/books/highlights/${highlightId}`, data)
			return response
		}

		if (contentType === "video") {
			const response = await api.put(`/videos/highlights/${highlightId}`, data)
			return response
		}

		// If content type is unknown, try both endpoints intelligently
		const endpoints = [
			{ name: "video", url: `/videos/highlights/${highlightId}` },
			{ name: "book", url: `/books/highlights/${highlightId}` },
		]

		let lastError = null

		for (const endpoint of endpoints) {
			try {
				const response = await api.put(endpoint.url, data)
				return response
			} catch (error) {
				lastError = error
				if (error.status === 404) {
				} else {
					throw error
				}
			}
		}
		throw lastError || new Error("Highlight not found")
	},

	/**
	 * Helper to get the correct API endpoint based on content type
	 */
	getEndpoint(contentType, contentId) {
		switch (contentType) {
			case "book":
				return `/books/${contentId}`
			case "pdf":
				// PDFs are tied to a book; persist highlights under the parent book
				return `/books/${contentId}`
			case "lesson":
				// Assuming lessons are part of courses
				return `/courses/lessons/${contentId}`
			case "video":
				return `/videos/${contentId}`
			default:
				throw new Error(`Unknown content type: ${contentType}`)
		}
	},
}
