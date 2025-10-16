/**
 * API synchronization utilities
 * Handles debounced syncing, offline queue, and retry logic
 */
import logger from "./logger"

// Debounce timers for different data types
const syncTimers = new Map()
const SYNC_DELAY = 2000 // 2 seconds - matches documentation
const MAX_RETRIES = 3
const RETRY_DELAY = 1000 // 1 second

// Offline queue for failed syncs
const offlineQueue = []
let isOnline = navigator.onLine

// Listen for online/offline events
window.addEventListener("online", () => {
	isOnline = true
	processOfflineQueue()
})

window.addEventListener("offline", () => {
	isOnline = false
})

/**
 * Main sync function with debouncing and retry logic
 * @param {string} resourceType - Type of resource (books, videos, etc.)
 * @param {string} resourceId - ID of the resource
 * @param {object} data - Data to sync
 */
export async function syncToAPI(resourceType, resourceId, data) {
	const syncKey = `${resourceType}:${resourceId}`

	// Clear existing timer
	if (syncTimers.has(syncKey)) {
		clearTimeout(syncTimers.get(syncKey))
	}

	// Set new debounced timer
	const timer = setTimeout(async () => {
		await performSync(resourceType, resourceId, data)
		syncTimers.delete(syncKey)
	}, SYNC_DELAY)

	syncTimers.set(syncKey, timer)
}

/**
 * Perform the actual sync operation
 */
async function performSync(resourceType, resourceId, data, retryCount = 0) {
	// Check if online
	if (!isOnline) {
		queueForOfflineSync(resourceType, resourceId, data)
		return
	}

	try {
		const endpoint = buildEndpoint(resourceType, resourceId, data)

		// If no endpoint is available for this data type, skip sync
		if (!endpoint) {
			// No sync endpoint for this resource type - skip silently
			return { skipped: true }
		}

		const method = determineMethod(resourceType, data)

		// Transform data for specific endpoint requirements
		let requestData = data
		if (resourceType === "books" && data.tocProgress) {
			// For book ToC progress updates, wrap in progress format expected by backend
			requestData = {
				tocProgress: data.tocProgress,
			}
		} else if (resourceType === "videos" && data.progress) {
			// For video progress updates, extract only the fields the backend expects
			requestData = {
				lastPosition: data.progress.lastPosition || data.progress.currentTime || 0,
			}
		} else if (
			resourceType === "videos" &&
			(data.progress ||
				data.lastPosition !== undefined ||
				data.currentTime !== undefined ||
				data.duration !== undefined)
		) {
			// Handle direct video progress data - filter to only valid backend fields
			requestData = {}
			if (data.progress?.lastPosition !== undefined) {
				requestData.lastPosition = data.progress.lastPosition
			} else if (data.progress?.currentTime !== undefined) {
				requestData.lastPosition = data.progress.currentTime
			} else if (data.lastPosition !== undefined) {
				requestData.lastPosition = data.lastPosition
			} else if (data.currentTime !== undefined) {
				requestData.lastPosition = data.currentTime
			}
			if (data.progress?.completionPercentage !== undefined) {
				requestData.completionPercentage = data.progress.completionPercentage
			} else if (data.completionPercentage !== undefined) {
				requestData.completionPercentage = data.completionPercentage
			}
		} else if (resourceType === "videos" && data.chapterStatus) {
			// For chapter status updates, extract the status
			requestData = {
				status: data.chapterStatus.status,
			}
		} else if (resourceType === "preferences") {
			// For preferences updates, wrap in expected format
			requestData = {
				preferences: data,
			}
		}

		const response = await fetch(endpoint, {
			method,
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(requestData),
		})

		if (!response.ok) {
			throw new Error(`Sync failed: ${response.statusText}`)
		}

		// Successfully synced - no need to log every sync
		return await response.json()
	} catch (error) {
		logger.error(`Sync failed for ${resourceType}:${resourceId}`, error)

		// Retry logic
		if (retryCount < MAX_RETRIES) {
			// Retrying sync after error
			await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY * (retryCount + 1)))
			return performSync(resourceType, resourceId, data, retryCount + 1)
		}

		// Max retries reached, queue for offline sync
		queueForOfflineSync(resourceType, resourceId, data)
		throw error
	}
}

/**
 * Build the API endpoint based on resource type and data
 */
function buildEndpoint(resourceType, resourceId, data) {
	const baseUrl = "/api/v1"

	switch (resourceType) {
		case "books":
			if (data.progress) {
				return `${baseUrl}/books/${resourceId}/progress`
			}
			if (data.tocProgress || data.tocProgressBatch) {
				return `${baseUrl}/books/${resourceId}/progress`
			}
			if (data.chapterStatus) {
				// Only sync chapter status for actual UUID chapter IDs, not ToC section IDs
				const chapterId = data.chapterStatus.chapterId
				if (chapterId?.startsWith("toc_")) {
					// This is a ToC section ID, not a chapter UUID - skip sync
					// Skip ToC section IDs - they don't have backend endpoints
					return null
				}
				return `${baseUrl}/books/${resourceId}/chapters/${chapterId}/status`
			}
			// For now, ignore other book sync attempts (like epubLocation, etc.)
			// These don't have backend endpoints yet
			return null

		case "videos":
			if (data.progress) {
				return `${baseUrl}/videos/${resourceId}/progress`
			}
			if (data.chapterStatus) {
				// Only sync chapter status for actual UUID chapter IDs, not description-based chapter IDs
				const chapterId = data.chapterStatus.chapterId
				if (chapterId && (chapterId.startsWith("chapter-") || chapterId.startsWith("toc_"))) {
					// This is a description-based chapter ID, not a UUID - skip sync
					// Skip description-based chapter IDs - they don't have backend endpoints
					return null
				}
				return `${baseUrl}/videos/${resourceId}/chapters/${chapterId}/status`
			}
			// Ignore other video sync attempts
			return null

		case "preferences": {
			// User preferences are now handled by auth context automatically
			// The backend will use the effective user ID from the request
			return `${baseUrl}/user/preferences`
		}

		case "courses":
			if (data.lessonStatus) {
				// Lesson progress sync flows through the unified progress service; skip duplicate API sync
				return null
			}
			// Ignore other course sync attempts
			return null

		default:
			// Don't throw error for unknown types, just skip sync
			// No sync handler for this resource type - skip silently
			return null
	}
}

/**
 * Determine HTTP method based on resource type and data
 */
function determineMethod(resourceType, data) {
	// Video progress updates use PATCH
	if (resourceType === "videos" && data.progress) {
		return "PATCH"
	}

	// Other progress updates use POST
	if (data.progress || data.nodeStatus || data.tocProgress) {
		return "POST"
	}

	// Chapter status updates use PUT
	if (data.chapterStatus) {
		return "PUT"
	}

	// Preferences use PUT
	if (resourceType === "preferences") {
		return "PUT"
	}

	// Default to POST for all updates for now
	return "POST"
}

/**
 * Queue sync operation for when back online
 */
function queueForOfflineSync(resourceType, resourceId, data) {
	const queueItem = {
		resourceType,
		resourceId,
		data,
		timestamp: Date.now(),
	}

	// Check if already queued (update if exists)
	const existingIndex = offlineQueue.findIndex(
		(item) => item.resourceType === resourceType && item.resourceId === resourceId
	)

	if (existingIndex >= 0) {
		offlineQueue[existingIndex] = queueItem
	} else {
		offlineQueue.push(queueItem)
	}

	// Save queue to localStorage
	localStorage.setItem("syncQueue", JSON.stringify(offlineQueue))

	// Queued for offline sync
}

/**
 * Process offline queue when back online
 */
async function processOfflineQueue() {
	if (offlineQueue.length === 0) return

	// Processing offline queue

	const queue = [...offlineQueue]
	offlineQueue.length = 0 // Clear queue

	for (const item of queue) {
		try {
			await performSync(item.resourceType, item.resourceId, item.data)
		} catch (error) {
			logger.error("Failed to sync queued item", error, { item })
			// Re-queue failed items
			queueForOfflineSync(item.resourceType, item.resourceId, item.data)
		}
	}

	// Update localStorage
	localStorage.setItem("syncQueue", JSON.stringify(offlineQueue))
}

/**
 * Load offline queue from localStorage on startup
 */
function loadOfflineQueue() {
	try {
		const saved = localStorage.getItem("syncQueue")
		if (saved) {
			const queue = JSON.parse(saved)

			// Validate queue data - filter out corrupted entries
			const validQueue = queue.filter((item) => {
				return (
					item &&
					typeof item.resourceType === "string" &&
					typeof item.resourceId === "string" &&
					item.data &&
					typeof item.data === "object"
				)
			})

			if (validQueue.length !== queue.length) {
				// Cleaned corrupted sync queue items
			}

			offlineQueue.push(...validQueue)

			// Process queue if online
			if (isOnline) {
				processOfflineQueue()
			}
		}
	} catch (error) {
		logger.error("Failed to load offline queue", error)
		// Clear corrupted queue
		localStorage.removeItem("syncQueue")
	}
}

// Load queue on startup
loadOfflineQueue()
