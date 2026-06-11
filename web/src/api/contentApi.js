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
 * @param {Object} [options]
 * @param {boolean} [options.force] - Delete a book even when courses still reference it
 * @returns {Promise<null>}
 */
export const deleteContent = async (contentType, contentId, { force = false } = {}) => {
	const mapped = mapContentType(contentType)
	const suffix = force ? "?force=true" : ""
	return api.delete(`/content/${mapped}/${contentId}${suffix}`)
}

/**
 * Read the BOOK_HAS_ATTACHMENTS conflict payload off a delete error, if present.
 * @param {Error} error - Error thrown by deleteContent
 * @returns {{attachmentCount: number, courseIds: string[]} | null}
 */
export const getBookAttachmentConflict = (error) => {
	if (error?.status !== 409) return null
	const payload = error?.data?.error
	if (payload?.code !== "BOOK_HAS_ATTACHMENTS") return null
	return {
		attachmentCount: Number(payload?.metadata?.attachmentCount ?? 0),
		courseIds: Array.isArray(payload?.metadata?.courseIds) ? payload.metadata.courseIds : [],
	}
}
