/**
 * Shared utilities for progress tracking across all content types
 */

/**
 * Dispatch a progress update event that the dashboard can listen to
 * @param {string} contentType - Type of content (course, video, book)
 * @param {string} contentId - ID of the content
 * @param {Object} progressData - Progress data to send
 */
export function dispatchProgressUpdate(contentType, contentId, progressData = {}) {
	if (typeof window === "undefined" || !contentId) {
		return
	}

	const toSnakeCase = (key) => key.replace(/([A-Z])/g, "_$1").toLowerCase()

	const resolveProgressValue = () => {
		if (typeof progressData.progress === "number") {
			return progressData.progress
		}

		if (typeof progressData.percentage === "number") {
			return progressData.percentage
		}

		if (typeof progressData.progress_percentage === "number") {
			return progressData.progress_percentage
		}

		const stats = progressData.progressStats || {}
		if (typeof stats.percentage === "number") {
			return stats.percentage
		}

		return undefined
	}

	const metadataSource =
		progressData.metadata && typeof progressData.metadata === "object"
			? progressData.metadata
			: progressData.progressStats && typeof progressData.progressStats === "object"
				? progressData.progressStats.metadata || {}
				: {}

	const normalizedMetadata = {}
	Object.entries(metadataSource).forEach(([key, value]) => {
		if (value === undefined) {
			return
		}

		const normalizedKey = key.includes("_") ? key : toSnakeCase(key)
		normalizedMetadata[normalizedKey] = value
	})

	if (!normalizedMetadata.content_type && contentType) {
		normalizedMetadata.content_type = contentType
	}

	if (progressData.refresh) {
		normalizedMetadata.refresh = true
	}

	window.dispatchEvent(
		new CustomEvent("progressUpdated", {
			detail: {
				contentId,
				progress: resolveProgressValue(),
				metadata: normalizedMetadata,
			},
		})
	)
}

/**
 * Dispatch a progress refresh event to trigger data refetch
 * @param {string} contentType - Type of content (course, video, book)
 * @param {string} contentId - ID of the content
 */
export function dispatchProgressRefresh(contentType, contentId) {
	dispatchProgressUpdate(contentType, contentId, { refresh: true })
}

/**
 * Calculate progress percentage from items
 * @param {Object} items - Object with item IDs as keys and completion status as values
 * @returns {Object} Progress data with percentage, totalItems, completedItems
 */
export function calculateProgressFromItems(items) {
	const itemIds = Object.keys(items)
	const totalItems = itemIds.length
	const completedItems = itemIds.filter((id) => items[id]).length
	const percentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

	return {
		percentage,
		totalItems,
		completedItems,
	}
}

/**
 * Log error with consistent formatting
 * @param {string} title - Error title
 * @param {string} description - Error description
 */
export function logError(_title, _description) {}

/**
 * Log sync error with consistent messaging
 */
export function logSyncError() {
	logError("Sync Error", "Progress saved locally but failed to sync to server")
}

/**
 * Track performance metrics for progress operations
 * @param {string} operation - Name of the operation
 * @param {Function} fn - Function to execute and measure
 * @returns {Promise} Result of the function
 */
export async function trackPerformance(_operation, fn) {
	const startTime = performance.now()

	try {
		const result = await fn()
		const duration = performance.now() - startTime

		// You could send this to analytics here
		if (duration > 1000) {
		}

		return result
	} catch (error) {
		const _duration = performance.now() - startTime
		throw error
	}
}

/**
 * Debounce function for API calls
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(fn, delay = 2000) {
	let timeoutId

	return function (...args) {
		clearTimeout(timeoutId)
		timeoutId = setTimeout(() => fn.apply(this, args), delay)
	}
}

/**
 * Batch multiple progress updates into a single operation
 * @param {Array} updates - Array of update objects with itemId and completed status
 * @returns {Object} Object with completed and incomplete item arrays
 */
export function batchProgressUpdates(updates) {
	const completed = []
	const incomplete = []

	for (const { itemId, completed: isCompleted } of updates) {
		if (isCompleted) {
			completed.push(itemId)
		} else {
			incomplete.push(itemId)
		}
	}

	return { completed, incomplete }
}

/**
 * Format progress for display
 * @param {number} percentage - Progress percentage
 * @param {number} completedItems - Number of completed items
 * @param {number} totalItems - Total number of items
 * @returns {string} Formatted progress string
 */
export function formatProgress(percentage, completedItems, totalItems) {
	return `${percentage}% (${completedItems}/${totalItems})`
}

/**
 * Check if progress data is valid
 * @param {Object} progress - Progress object to validate
 * @returns {boolean} Whether the progress data is valid
 */
export function isValidProgress(progress) {
	return (
		progress &&
		typeof progress.percentage === "number" &&
		typeof progress.totalItems === "number" &&
		typeof progress.completedItems === "number" &&
		progress.items &&
		typeof progress.items === "object"
	)
}

/**
 * Get empty progress object with standard structure
 * @returns {Object} Empty progress object
 */
export function getEmptyProgress() {
	return {
		percentage: 0,
		totalItems: 0,
		completedItems: 0,
		items: {},
	}
}

// Legacy functions for backward compatibility
export function getVideoProgress(video, currentTime = null) {
	if (currentTime !== null && video?.duration > 0) {
		return Math.round((currentTime / video.duration) * 100)
	}
	return Math.round(video?.progress || video?.completionPercentage || 0)
}

export function getBookProgress(book, progressStats = null) {
	if (progressStats?.percentage > 0) {
		return Math.round(progressStats.percentage)
	}
	return Math.round(book?.progressPercentage || 0)
}

export function formatProgressText(percentage, _type = "content") {
	const rounded = Math.round(percentage)
	return `${rounded}%`
}

export function isCompleted(percentage) {
	return percentage >= 100
}

export function getProgressStatus(percentage) {
	if (percentage >= 100) return "completed"
	if (percentage > 0) return "in_progress"
	return "not_started"
}
