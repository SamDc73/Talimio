/**
 * Secure API client with authentication and security monitoring
 */

const BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

// In-flight request cache for deduplication
const inFlightRequests = new Map()

// Helper function to handle API responses
const handleResponse = async (response, endpoint) => {
	if (!response.ok) {
		let errorData
		try {
			errorData = await response.json()
		} catch (_e) {
			errorData = { message: response.statusText }
		}

		if (response.status === 401 && !endpoint.includes("/auth/")) {
			if (window.location.pathname !== "/auth") {
				window.location.href = "/auth"
			}
		}

		const error = new Error(`API Error: ${response.status} ${errorData?.message || response.statusText}`)
		error.status = response.status
		error.data = errorData
		throw error
	}

	return response.json()
}

// Request wrapper with deduplication
const secureRequest = async (method, endpoint, data = null, options = {}) => {
	// Create cache key for deduplication (GET requests only)
	if (method === "GET") {
		const cacheKey = `${method}:${endpoint}:${JSON.stringify(options)}`

		// If request is already in flight, return the existing promise
		if (inFlightRequests.has(cacheKey)) {
			return inFlightRequests.get(cacheKey)
		}

		// Create and cache the request promise
		const requestPromise = executeRequest(method, endpoint, data, options).finally(() => {
			// Clean up cache entry when request completes
			inFlightRequests.delete(cacheKey)
		})

		inFlightRequests.set(cacheKey, requestPromise)
		return requestPromise
	}

	// For non-GET requests, execute directly
	return executeRequest(method, endpoint, data, options)
}

// Extract the actual request execution logic
const executeRequest = async (method, endpoint, data = null, options = {}) => {
	const makeRequest = async () => {
		const requestOptions = {
			method,
			headers: {
				"Content-Type": "application/json",
				...(options.headers || {}),
			},
			credentials: "include", // Include httpOnly cookies
			cache: method === "GET" ? "no-store" : undefined,
			...options,
		}

		if (data && method !== "GET") {
			requestOptions.body = JSON.stringify(data)
		}

		return fetch(`${BASE_URL}${endpoint}`, requestOptions)
	}

	const response = await makeRequest()
	return handleResponse(response, endpoint)
}

// Main API client
export const api = {
	async get(endpoint, options = {}) {
		return secureRequest("GET", endpoint, null, options)
	},

	async post(endpoint, data = null, options = {}) {
		return secureRequest("POST", endpoint, data, options)
	},

	async put(endpoint, data = null, options = {}) {
		return secureRequest("PUT", endpoint, data, options)
	},

	async patch(endpoint, data = null, options = {}) {
		return secureRequest("PATCH", endpoint, data, options)
	},

	async delete(endpoint, options = {}) {
		return secureRequest("DELETE", endpoint, null, options)
	},
}
