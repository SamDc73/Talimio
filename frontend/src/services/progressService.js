/**
 * Base API URL for progress endpoints
 * @constant
 */
const API_BASE = '/api/v1/progress';

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
    if (error.name === 'AbortError') {
      throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`);
    }
    throw error;
  }
}

/**
 * Batch multiple progress requests
 * @param {string[]} nodeIds - Array of node IDs
 * @param {string} userId - The user ID
 * @returns {Promise<Object>} Map of nodeId to progress data
 */
async function batchProgressRequests(nodeIds, userId) {
  const uniqueIds = [...new Set(nodeIds)];
  const cacheKey = `${userId}-${uniqueIds.sort().join(',')}`;

  // Check cache first
  const cachedData = progressCache.get(cacheKey);
  if (cachedData) {
    return cachedData;
  }

  try {
    const response = await fetchWithTimeout(
      `${API_BASE}/user/${userId}/batch`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeIds: uniqueIds }),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch batch progress: ${response.statusText}`);
    }

    const data = await response.json();
    progressCache.set(cacheKey, data);
    return data;
  } catch (error) {
    console.error('Error fetching batch progress:', error);
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
export async function getNodeProgress(userId, nodeId) {
  const cacheKey = `${userId}-${nodeId}`;
  const cachedData = progressCache.get(cacheKey);
  if (cachedData) {
    return cachedData;
  }

  try {
    const response = await fetchWithTimeout(`${API_BASE}/user/${userId}/node/${nodeId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch progress: ${response.statusText}`);
    }
    const data = await response.json();
    progressCache.set(cacheKey, data);
    return data;
  } catch (error) {
    console.error('Error fetching node progress:', error);
    throw error;
  }
}

/**
 * Get all progress records for a user
 * @param {string} userId - The ID of the user
 * @returns {Promise<Progress[]>} Array of progress records
 * @throws {Error} If the request fails
 */
export async function getUserProgress(userId) {
  const cacheKey = `user-${userId}`;
  const cachedData = progressCache.get(cacheKey);
  if (cachedData) {
    return cachedData;
  }

  try {
    const response = await fetchWithTimeout(`${API_BASE}/user/${userId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch user progress: ${response.statusText}`);
    }
    const data = await response.json();
    progressCache.set(cacheKey, data);
    return data;
  } catch (error) {
    console.error('Error fetching user progress:', error);
    throw error;
  }
}

/**
 * Create a new progress record for a node
 * @param {string} nodeId - The ID of the node
 * @param {Object} progressData - The progress data to create
 * @returns {Promise<Progress>} The created progress record
 * @throws {Error} If the request fails
 */
export async function createNodeProgress(nodeId, progressData) {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE}/node/${nodeId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(progressData),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to create progress: ${response.statusText}`);
    }
    const data = await response.json();

    // Invalidate relevant cache entries
    progressCache.clear();
    return data;
  } catch (error) {
    console.error('Error creating node progress:', error);
    throw error;
  }
}

/**
 * Update an existing progress record
 * @param {string} progressId - The ID of the progress record to update
 * @param {Object} updateData - The data to update
 * @returns {Promise<Progress>} The updated progress record
 * @throws {Error} If the request fails
 */
export async function updateProgress(progressId, updateData) {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE}/${progressId}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to update progress: ${response.statusText}`);
    }
    const data = await response.json();

    // Invalidate relevant cache entries
    progressCache.clear();
    return data;
  } catch (error) {
    console.error('Error updating progress:', error);
    throw error;
  }
}

// Export for testing
export const _progressCache = progressCache;
export const _batchProgressRequests = batchProgressRequests;
