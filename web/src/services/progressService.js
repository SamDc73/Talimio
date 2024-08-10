import { api } from "../lib/api"

/**
 * Cache configuration
 * @constant
 */
const CACHE_CONFIG = {
	maxAge: 5 * 60 * 1000, // 5 minutes
	maxSize: 1000, // Maximum number of items to cache
}

/**
 * Simple in-memory cache implementation
 */
class Cache {
	constructor(maxAge, maxSize) {
		this.maxAge = maxAge
		this.maxSize = maxSize
		this.cache = new Map()
	}

	set(key, value) {
		if (this.cache.size >= this.maxSize) {
			// Remove oldest entry
			const oldestKey = this.cache.keys().next().value
			this.cache.delete(oldestKey)
		}
		this.cache.set(key, {
			value,
			timestamp: Date.now(),
		})
	}

	get(key) {
		const entry = this.cache.get(key)
		if (!entry) return null

		if (Date.now() - entry.timestamp > this.maxAge) {
			this.cache.delete(key)
			return null
		}

		return entry.value
	}

	clear() {
		this.cache.clear()
	}
}

// Initialize cache
const progressCache = new Cache(CACHE_CONFIG.maxAge, CACHE_CONFIG.maxSize)

/**
 * Get progress for a specific module
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module
 * @returns {Promise<Module>} The module data
 * @throws {Error} If the request fails
 */
export async function getModuleProgress(courseId, moduleId) {
	const cacheKey = `course-${courseId}-module-${moduleId}`
	const cachedData = progressCache.get(cacheKey)
	if (cachedData) {
		return cachedData
	}
	const data = await api.get(`/api/v1/courses/${courseId}/modules/${moduleId}`)
	progressCache.set(cacheKey, data)
	return data
}

/**
 * Get modules for a course with their progress
 * @param {string} courseId - The ID of the course
 * @returns {Promise<Module[]>} Array of modules with progress
 * @throws {Error} If the request fails
 */
export async function getCourseModules(courseId) {
	const cacheKey = `course-${courseId}-modules`
	const cachedData = progressCache.get(cacheKey)
	if (cachedData) {
		return cachedData
	}
	const data = await api.get(`/api/v1/courses/${courseId}/modules`)
	progressCache.set(cacheKey, data)
	return data
}

/**
 * Update module status
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} The update response
 * @throws {Error} If the request fails
 */
export async function updateModuleStatus(courseId, moduleId, status) {
	const data = await api.patch(`/api/v1/courses/${courseId}/modules/${moduleId}`, { status })

	// Invalidate relevant cache entries
	progressCache.clear()
	return data
}

/**
 * Update lesson status
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module (optional, for compatibility)
 * @param {string} lessonId - The ID of the lesson
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} The update response
 * @throws {Error} If the request fails
 */
export async function updateLessonStatus(courseId, _moduleId, lessonId, status) {
	const data = await api.patch(`/api/v1/courses/${courseId}/lessons/${lessonId}/status`, { status })

	// Invalidate relevant cache entries
	progressCache.clear()
	return data
}

/**
 * Update a module
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module to update
 * @param {Object} updateData - The data to update
 * @returns {Promise<Module>} The updated module
 * @throws {Error} If the request fails
 */
export async function updateModule(courseId, moduleId, updateData) {
	const data = await api.patch(`/api/v1/courses/${courseId}/modules/${moduleId}`, updateData)

	// Invalidate relevant cache entries
	progressCache.clear()
	return data
}

// Export for testing
export const _progressCache = progressCache
