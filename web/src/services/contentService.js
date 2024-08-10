/**
 * Content service for archive/unarchive operations
 */

import { api } from "@/lib/apiClient"

/**
 * Archive a content item
 * @param {string} contentType - Type of content (book, youtube, flashcards, course)
 * @param {string} contentId - ID of the content item
 * @returns {Promise<{message: string}>}
 */
export const archiveContent = async (contentType, contentId) => {
	const response = await api.patch(`/content/${contentType}/${contentId}/archive`)
	return response
}

/**
 * Unarchive a content item
 * @param {string} contentType - Type of content (book, youtube, flashcards, course)
 * @param {string} contentId - ID of the content item
 * @returns {Promise<{message: string}>}
 */
export const unarchiveContent = async (contentType, contentId) => {
	const response = await api.patch(`/content/${contentType}/${contentId}/unarchive`)
	return response
}

/**
 * Get content statistics including archive counts
 * @returns {Promise<Object>} Content statistics
 */
export const getContentStats = async () => {
	const response = await api.get("/content/stats")
	return response
}

/**
 * List archived content
 * @param {Object} params - Query parameters
 * @param {string} params.search - Search term
 * @param {string} params.contentType - Content type filter
 * @param {number} params.page - Page number
 * @param {number} params.pageSize - Items per page
 * @returns {Promise<Object>} Archived content list
 */
export const listArchivedContent = async (params = {}) => {
	const queryParams = new URLSearchParams()

	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined && value !== null && value !== "") {
			queryParams.append(key, value.toString())
		}
	})

	const response = await api.get(`/content/archived?${queryParams.toString()}`)
	return response
}
