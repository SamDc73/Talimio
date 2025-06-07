/**
 * Service for managing video chapters and their progress
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/**
 * Fetch chapters for a video
 * @param {string} videoUuid - The UUID of the video
 * @returns {Promise<Array>} Array of chapters
 */
export async function getVideoChapters(videoUuid) {
  try {
    const response = await fetch(`${API_BASE}/videos/${videoUuid}/chapters`);
    if (!response.ok) {
      throw new Error(`Failed to fetch video chapters: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching video chapters:', error);
    throw error;
  }
}

/**
 * Get a specific chapter
 * @param {string} videoUuid - The UUID of the video
 * @param {string} chapterId - The ID of the chapter
 * @returns {Promise<Object>} Chapter data
 */
export async function getVideoChapter(videoUuid, chapterId) {
  try {
    const response = await fetch(`${API_BASE}/videos/${videoUuid}/chapters/${chapterId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch chapter: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching chapter:', error);
    throw error;
  }
}

/**
 * Update chapter status
 * @param {string} videoUuid - The UUID of the video
 * @param {string} chapterId - The ID of the chapter
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} Update response
 */
export async function updateVideoChapterStatus(videoUuid, chapterId, status) {
  try {
    const response = await fetch(`${API_BASE}/videos/${videoUuid}/chapters/${chapterId}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    });

    if (!response.ok) {
      throw new Error(`Failed to update chapter status: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error updating chapter status:', error);
    throw error;
  }
}

/**
 * Extract chapters from video
 * @param {string} videoUuid - The UUID of the video
 * @returns {Promise<Object>} Extraction response
 */
export async function extractVideoChapters(videoUuid) {
  try {
    const response = await fetch(`${API_BASE}/videos/${videoUuid}/extract-chapters`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to extract chapters: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error extracting chapters:', error);
    throw error;
  }
}