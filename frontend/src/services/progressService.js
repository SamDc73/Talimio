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
 * @property {string} nodeId - The ID of the node
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
 * Get progress for a specific user and node
 * @param {string} userId - The ID of the user
 * @param {string} nodeId - The ID of the node
 * @returns {Promise<Progress>} The progress data
 * @throws {Error} If the request fails
 */
export async function getNodeProgress(nodeId) {
	const cacheKey = `node-${nodeId}`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(`${API_BASE}/nodes/${nodeId}`);
		if (!response.ok) {
			throw new Error(`Failed to fetch node: ${response.statusText}`);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching node:", error);
		throw error;
	}
}

/**
 * Get nodes for a roadmap with their progress
 * @param {string} roadmapId - The ID of the roadmap
 * @returns {Promise<Node[]>} Array of nodes with progress
 * @throws {Error} If the request fails
 */
export async function getRoadmapNodes(roadmapId) {
	const cacheKey = `roadmap-nodes-${roadmapId}`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/roadmaps/${roadmapId}/nodes`,
		);
		if (!response.ok) {
			throw new Error(`Failed to fetch roadmap nodes: ${response.statusText}`);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching roadmap nodes:", error);
		throw error;
	}
}

/**
 * Update node status
 * @param {string} nodeId - The ID of the node
 * @param {string} status - The new status (not_started, in_progress, completed)
 * @returns {Promise<Object>} The update response
 * @throws {Error} If the request fails
 */
export async function updateNodeStatus(nodeId, status) {
	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/nodes/${nodeId}/status`,
			{
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			},
		);

		if (!response.ok) {
			throw new Error(`Failed to update node status: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.clear();
		return data;
	} catch (error) {
		console.error("Error updating node status:", error);
		throw error;
	}
}

/**
 * Update a node
 * @param {string} nodeId - The ID of the node to update
 * @param {Object} updateData - The data to update
 * @returns {Promise<Node>} The updated node
 * @throws {Error} If the request fails
 */
export async function updateNode(nodeId, updateData) {
	try {
		const response = await fetchWithTimeout(`${API_BASE}/nodes/${nodeId}`, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(updateData),
		});

		if (!response.ok) {
			throw new Error(`Failed to update node: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.clear();
		return data;
	} catch (error) {
		console.error("Error updating node:", error);
		throw error;
	}
}

// Export for testing
export const _progressCache = progressCache;
