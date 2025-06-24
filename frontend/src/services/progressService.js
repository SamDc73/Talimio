/**
 * Base API URL for progress endpoints
 * @constant
 */
const API_BASE = "/api/v1";

/**
 * Default timeout for API requests in milliseconds
 * @constant
 */
const REQUEST_TIMEOUT = 7000;

/**
 * Cache configuration
 * @constant
 */
const CACHE_CONFIG = {
	maxAge: 5 * 60 * 1000, // 5 minutes
	maxSize: 1000, // Maximum number of items to cache
};

/**
 * Simple in-memory cache implementation
 */
class Cache {
	constructor(maxAge, maxSize) {
		this.maxAge = maxAge;
		this.maxSize = maxSize;
		this.cache = new Map();
	}

	set(key, value) {
		if (this.cache.size >= this.maxSize) {
			// Remove oldest entry
			const oldestKey = this.cache.keys().next().value;
			this.cache.delete(oldestKey);
		}
		this.cache.set(key, {
			value,
			timestamp: Date.now(),
		});
	}

	get(key) {
		const entry = this.cache.get(key);
		if (!entry) return null;

		if (Date.now() - entry.timestamp > this.maxAge) {
			this.cache.delete(key);
			return null;
		}

		return entry.value;
	}

	clear() {
		this.cache.clear();
	}
}

// Initialize cache
const progressCache = new Cache(CACHE_CONFIG.maxAge, CACHE_CONFIG.maxSize);

/**
 * @typedef {Object} Progress
 * @property {string} id - The unique identifier for the progress record
 * @property {string} userId - The ID of the user
 * @property {string} moduleId - The ID of the module
 * @property {string} status - The current progress status
 * @property {Date} updatedAt - Last update timestamp
 */

/**
 * Fetch with timeout wrapper
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise} The fetch promise with timeout
 */
async function fetchWithTimeout(url, options = {}) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
		});
		clearTimeout(timeout);
		return response;
	} catch (error) {
		clearTimeout(timeout);
		if (error.name === "AbortError") {
			throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`);
		}
		throw error;
	}
}

/**
 * Get progress for a specific module
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module
 * @returns {Promise<Module>} The module data
 * @throws {Error} If the request fails
 */
export async function getModuleProgress(courseId, moduleId) {
	const cacheKey = `course-${courseId}-module-${moduleId}`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(`${API_BASE}/courses/${courseId}/modules/${moduleId}`);
		if (!response.ok) {
			throw new Error(`Failed to fetch module: ${response.statusText}`);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching module:", error);
		throw error;
	}
}

/**
 * Get modules for a course with their progress
 * @param {string} courseId - The ID of the course
 * @returns {Promise<Module[]>} Array of modules with progress
 * @throws {Error} If the request fails
 */
export async function getCourseModules(courseId) {
	const cacheKey = `course-${courseId}-modules`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/modules`,
		);
		if (!response.ok) {
			throw new Error(`Failed to fetch course modules: ${response.statusText}`);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching course modules:", error);
		throw error;
	}
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
	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/modules/${moduleId}`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			},
		);

		if (!response.ok) {
			throw new Error(`Failed to update module status: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.clear();
		return data;
	} catch (error) {
		console.error("Error updating module status:", error);
		throw error;
	}
}


/**
 * Update lesson status
 * @param {string} courseId - The ID of the course
 * @param {string} moduleId - The ID of the module
 * @param {string} lessonId - The ID of the lesson
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} The update response
 * @throws {Error} If the request fails
 */
export async function updateLessonStatus(courseId, moduleId, lessonId, status) {
	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/status`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			},
		);

		if (!response.ok) {
			throw new Error(`Failed to update lesson status: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.clear();
		return data;
	} catch (error) {
		console.error("Error updating lesson status:", error);
		throw error;
	}
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
	try {
		const response = await fetchWithTimeout(`${API_BASE}/courses/${courseId}/modules/${moduleId}`, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(updateData),
		});

		if (!response.ok) {
			throw new Error(`Failed to update module: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.clear();
		return data;
	} catch (error) {
		console.error("Error updating module:", error);
		throw error;
	}
}


// Export for testing
export const _progressCache = progressCache;
