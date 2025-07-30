/**
 * Service for managing video chapters and their progress
 */
import { api } from "@/lib/apiClient";

const _API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/**
 * Fetch chapters for a video
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Array>} Array of chapters
 */
export async function getVideoChapters(videoId) {
	try {
		const chapters = await api.get(`/videos/${videoId}/chapters`);
		return chapters || [];
	} catch (error) {
		console.error("Error fetching video chapters:", error);
		// Don't throw - return empty array so the sidebar can still render
		return [];
	}
}

/**
 * Get a specific chapter
 * @param {string} videoId - The ID of the video
 * @param {string} chapterId - The ID of the chapter
 * @returns {Promise<Object>} Chapter data
 */
export async function getVideoChapter(videoId, chapterId) {
	try {
		return await api.get(`/videos/${videoId}/chapters/${chapterId}`);
	} catch (error) {
		console.error("Error fetching chapter:", error);
		throw error;
	}
}

/**
 * Update chapter status
 * @param {string} videoId - The ID of the video
 * @param {string} chapterId - The ID of the chapter
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} Update response
 */
export async function updateVideoChapterStatus(videoId, chapterId, status) {
	try {
		// Check if this is a timestamp-based chapter ID (like "chapter-70")
		const isTimestampId = chapterId.startsWith("chapter-");

		if (isTimestampId) {
			// For timestamp-based chapters, we can't update individual chapter status
			// These are extracted from description and not stored in DB
			// Return a mock success response
			return {
				success: true,
				message: "Chapter status updated locally",
				chapterId,
				status,
			};
		} else {
			// For UUID chapters, use the chapters endpoint
			return await api.put(`/videos/${videoId}/chapters/${chapterId}/status`, {
				status,
			});
		}
	} catch (error) {
		console.error("Error updating chapter status:", error);
		throw error;
	}
}

/**
 * Extract chapters from video
 * @param {string} videoId - The ID of the video
 * @returns {Promise<Object>} Extraction response
 */
export async function extractVideoChapters(videoId) {
	try {
		return await api.post(`/videos/${videoId}/extract-chapters`);
	} catch (error) {
		console.error("Error extracting chapters:", error);
		throw error;
	}
}

/**
 * Sync chapter progress from web app to backend
 * @param {string} videoId - The ID of the video
 * @param {string[]} completedChapterIds - Array of completed chapter IDs
 * @param {number} totalChapters - Total number of chapters
 * @returns {Promise<Object>} Updated video data
 */
export async function syncVideoChapterProgress(
	videoId,
	completedChapterIds,
	totalChapters,
) {
	try {
		return await api.post(`/videos/${videoId}/sync-chapter-progress`, {
			completedChapterIds: completedChapterIds,
			totalChapters: totalChapters,
		});
	} catch (error) {
		console.error("Error syncing chapter progress:", error);
		throw error;
	}
}
