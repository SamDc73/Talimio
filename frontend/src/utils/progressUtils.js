/**
 * Utility functions for progress calculations across videos and PDFs
 *
 * UNIFIED PROGRESS PHILOSOPHY:
 * - Videos: Time-based (currentTime/duration * 100) - smooth linear progress
 * - PDFs: Chapter-weighted sections - major chapters worth 5x more for meaningful progress
 * - Courses: Lesson-based (completedLessons/totalLessons * 100) - each lesson is a meaningful chunk
 *
 * This ensures consistent progress feel across all content types while respecting their unique structures.
 */

/**
 * Get standardized progress percentage for videos
 * @param {Object} video - Video object with progress data
 * @param {number} currentTime - Current playback time (for live calculation)
 * @returns {number} Progress percentage (0-100)
 */
export function getVideoProgress(video, currentTime = null) {
	// If we have real-time current time and duration, calculate live progress
	if (currentTime !== null && video?.duration > 0) {
		return Math.round((currentTime / video.duration) * 100);
	}

	// Otherwise use stored progress
	return Math.round(video?.progress || video?.completionPercentage || 0);
}

/**
 * Get standardized progress percentage for books/PDFs
 * @param {Object} book - Book object with progress data
 * @param {Object} progressStats - Progress statistics from ToC system
 * @returns {number} Progress percentage (0-100)
 */
export function getBookProgress(book, progressStats = null) {
	// Use ToC-based progress if available (more accurate)
	if (progressStats?.percentage > 0) {
		return Math.round(progressStats.percentage);
	}

	// Fall back to page-based progress (less accurate but still useful)
	return Math.round(book?.progressPercentage || 0);
}

/**
 * Format progress display text
 * @param {number} percentage - Progress percentage
 * @param {string} type - Content type (video, book, course)
 * @returns {string} Formatted progress text
 */
export function formatProgressText(percentage, _type = "content") {
	const rounded = Math.round(percentage);
	return `${rounded}%`;
}

/**
 * Determine if content is completed
 * @param {number} percentage - Progress percentage
 * @returns {boolean} Whether content is completed
 */
export function isCompleted(percentage) {
	return percentage >= 100;
}

/**
 * Get progress status for API calls
 * @param {number} percentage - Progress percentage
 * @returns {string} Status string
 */
export function getProgressStatus(percentage) {
	if (percentage >= 100) return "completed";
	if (percentage > 0) return "in_progress";
	return "not_started";
}
