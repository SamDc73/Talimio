/**
 * Content service for common content operations (archive/unarchive/delete).
 */

import { api } from "@/lib/apiClient"

// Map frontend types to backend ContentType enum
const mapContentType = (type) => {
	const map = {
		video: "youtube",
		youtube: "youtube",
		book: "book",
		course: "course",
	}
	return map[type] || type
}

/**
 * Archive a content item
 * @param {string} contentType - Type of content (book, youtube, course)
 * @param {string} contentId - ID of the content item
 * @returns {Promise<{message: string}>}
 */
export const archiveContent = async (contentType, contentId) => {
	const mapped = mapContentType(contentType)
	const response = await api.patch(`/content/${mapped}/${contentId}/archive`)
	return response
}

/**
 * Unarchive a content item
 * @param {string} contentType - Type of content (book, youtube, course)
 * @param {string} contentId - ID of the content item
 * @returns {Promise<{message: string}>}
 */
export const unarchiveContent = async (contentType, contentId) => {
	const mapped = mapContentType(contentType)
	const response = await api.patch(`/content/${mapped}/${contentId}/unarchive`)
	return response
}

/**
 * Delete a content item
 * @param {string} contentType - Type of content (book, youtube, course)
 * @param {string} contentId - ID of the content item
 * @returns {Promise<null>}
 */
export const deleteContent = async (contentType, contentId) => {
	const mapped = mapContentType(contentType)
	return api.delete(`/content/${mapped}/${contentId}`)
}
