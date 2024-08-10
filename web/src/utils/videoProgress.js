/**
 * Utility functions for video progress calculations
 */

/**
 * Calculate video progress percentage
 * @param {number} currentTime - Current playback time in seconds
 * @param {number} duration - Total video duration in seconds
 * @returns {number} Progress percentage (0-100)
 */
export function calculateVideoProgress(currentTime, duration) {
	if (!duration || duration <= 0) return 0
	return Math.round((currentTime / duration) * 100)
}

/**
 * Format duration in seconds to MM:SS or HH:MM:SS format
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string
 */
export function formatDuration(seconds) {
	if (!seconds || seconds < 0) return "0:00"

	const hours = Math.floor(seconds / 3600)
	const minutes = Math.floor((seconds % 3600) / 60)
	const secs = Math.floor(seconds % 60)

	if (hours > 0) {
		return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
	}

	return `${minutes}:${secs.toString().padStart(2, "0")}`
}

/**
 * Get progress display text
 * @param {number} currentTime - Current playback time in seconds
 * @param {number} duration - Total video duration in seconds
 * @returns {string} Progress display text like "5:30 / 10:00 (55%)"
 */
export function getProgressDisplayText(currentTime, duration) {
	const progress = calculateVideoProgress(currentTime, duration)
	return `${formatDuration(currentTime)} / ${formatDuration(duration)} (${progress}%)`
}
