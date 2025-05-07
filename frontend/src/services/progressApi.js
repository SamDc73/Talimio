/**
 * Progress API service for interacting with the backend progress endpoints
 */

const API_BASE = '/api/v1/progress';

/**
 * Update a lesson's completion status
 * 
 * @param {string} lessonId - The ID of the lesson to update
 * @param {string} status - The status to set ('not_started', 'in_progress', 'done')
 * @returns {Promise<Object>} - The updated lesson status
 */
export const updateLessonStatus = async (lessonId, status) => {
  try {
    const response = await fetch(`${API_BASE}/lesson/${lessonId}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to update lesson status');
    }

    return response.json();
  } catch (error) {
    console.error('Error updating lesson status:', error);
    throw error;
  }
};

/**
 * Get all lesson statuses for a course
 * 
 * @param {string} courseId - The ID of the course
 * @returns {Promise<Object>} - Object containing lesson statuses
 */
export const getLessonStatuses = async (courseId) => {
  try {
    const response = await fetch(`${API_BASE}/course/${courseId}/lessons`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to fetch lesson statuses');
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching lesson statuses:', error);
    throw error;
  }
};

/**
 * Get overall course progress
 * 
 * @param {string} courseId - The ID of the course
 * @returns {Promise<Object>} - Object containing course progress information
 */
export const getCourseProgress = async (courseId) => {
  try {
    const response = await fetch(`${API_BASE}/course/${courseId}`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to fetch course progress');
    }

    return response.json();
  } catch (error) {
    console.error('Error fetching course progress:', error);
    throw error;
  }
};
