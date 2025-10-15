/**
 * Service for managing videos, chapters and their progress
 */
import { api } from "@/lib/apiClient"

const _API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1"

/**
 * Get a video by ID (with authentication)
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Object>} Video data
 */
export async function getVideo(videoId) {
	return await api.get(`/videos/${videoId}`)
}

/**
 * Get video details including chapters and transcript info (optimized)
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Object>} Video details with chapters and transcript info
 */
export async function getVideoDetails(videoId) {
	return await api.get(`/videos/${videoId}/details`)
}

/**
 * Create a new video
 * @param {string} url - YouTube URL
 * @returns {Promise<Object>} Created video data
 */
export async function createVideo(url) {
	return await api.post("/videos", { url })
}

/**
 * Get all videos (with authentication)
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} Videos list response
 */
export async function getVideos(params = {}) {
	const queryString = new URLSearchParams(params).toString()
	const endpoint = queryString ? `/videos?${queryString}` : "/videos"
	return await api.get(endpoint)
}

/**
 * Get video transcript
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Object>} Transcript data
 */
export async function getVideoTranscript(videoId) {
	return await api.get(`/videos/${videoId}/transcript`)
}

/**
 * Fetch chapters for a video
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Array>} Array of chapters
 */
export async function getVideoChapters(videoId) {
	try {
		const chapters = await api.get(`/videos/${videoId}/chapters`)
		return chapters || []
	} catch (error) {
		// Log authentication errors for debugging
		if (error.status === 401) {
		} else if (error.status !== 404) {
		}
		// Don't throw - return empty array so the sidebar can still render
		return []
	}
}

/**
 * Get a specific chapter
 * @param {string} videoId - The ID of the video
 * @param {string} chapterId - The ID of the chapter
 * @returns {Promise<Object>} Chapter data
 */
export async function getVideoChapter(videoId, chapterId) {
	return await api.get(`/videos/${videoId}/chapters/${chapterId}`)
}

/**
 * Update chapter status
 * @param {string} videoId - The ID of the video
 * @param {string} chapterId - The ID of the chapter
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} Update response
 */
export async function updateVideoChapterStatus(videoId, chapterId, status) {
	// Check if this is a timestamp-based chapter ID (like "chapter-70")
	const isTimestampId = chapterId.startsWith("chapter-")

	if (isTimestampId) {
		// For timestamp-based chapters, we can't update individual chapter status
		// These are extracted from description and not stored in DB
		// Return a mock success response
		return {
			success: true,
			message: "Chapter status updated locally",
			chapterId,
			status,
		}
	}
	// For UUID chapters, use the chapters endpoint
	return await api.put(`/videos/${videoId}/chapters/${chapterId}/status`, {
		status,
	})
}

/**
 * Extract chapters from video
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Object>} Extraction response
 */
export async function extractVideoChapters(videoId) {
	return await api.post(`/videos/${videoId}/extract-chapters`)
}

/**
 * Sync chapter progress from web app to backend
 * @param {string} videoId - The ID of the video
 * @param {string[]} completedChapterIds - Array of completed chapter IDs
 * @param {number} totalChapters - Total number of chapters
 * @returns {Promise<Object>} Updated video data
 */
export async function syncVideoChapterProgress(videoId, completedChapterIds, totalChapters) {
	return await api.post(`/videos/${videoId}/sync-chapter-progress`, {
		completedChapterIds: completedChapterIds,
		totalChapters: totalChapters,
	})
}
