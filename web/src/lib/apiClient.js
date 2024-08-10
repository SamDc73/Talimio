/**
 * Secure API client with authentication and security monitoring
 */
import useAppStore from "../stores/useAppStore.js"
import { securityMonitor } from "../utils/securityConfig.js"

const BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

// Auth headers not needed - using httpOnly cookies!

// Token refresh state
let isRefreshing = false
let refreshSubscribers = []

// Subscribe to token refresh completion
const subscribeTokenRefresh = (callback) => {
	refreshSubscribers.push(callback)
}

// Notify all subscribers when token refresh completes
const onTokenRefreshed = () => {
	refreshSubscribers.forEach((callback) => callback())
	refreshSubscribers = []
}

// Refresh the access token
const refreshToken = async () => {
	if (isRefreshing) {
		// Wait for the ongoing refresh to complete
		return new Promise((resolve) => {
			subscribeTokenRefresh(() => resolve())
		})
	}

	isRefreshing = true

	try {
		const response = await fetch(`${BASE_URL}/auth/refresh`, {
			method: "POST",
			credentials: "include", // Include cookies
			headers: {
				"Content-Type": "application/json",
			},
		})

		if (response.ok) {
			onTokenRefreshed()
			return true
		}

		// Refresh failed - user needs to login again
		return false
	} catch (_error) {
		return false
	} finally {
		isRefreshing = false
	}
}

// Helper function to handle API responses
const handleResponse = async (response, endpoint, retryRequest) => {
	if (!response.ok) {
		let errorData
		try {
			errorData = await response.json()
		} catch (_e) {
			errorData = { message: response.statusText }
		}

		// Handle auth failures
		if (response.status === 401 && !endpoint.includes("/auth/")) {
			const refreshSuccess = await refreshToken()

			if (refreshSuccess && retryRequest) {
				// Retry the original request
				const retryResponse = await retryRequest()
				return handleResponse(retryResponse, endpoint, null)
			}
			// Clear user from store (cookies are cleared by server)
			const { clearUser } = useAppStore.getState()
			clearUser()
			// Redirect to auth page if we're in an auth-enabled environment
			const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"
			if (authEnabled && window.location.pathname !== "/auth") {
				window.location.href = "/auth"
			}
		}

		const error = new Error(`API Error: ${response.status} ${errorData?.message || response.statusText}`)
		error.status = response.status
		error.data = errorData
		throw error
	}

	// Handle responses with no content
	if (response.status === 204 || response.headers.get("content-length") === "0") {
		return null
	}

	return response.json()
}

// Security-enhanced request wrapper
const secureRequest = async (method, endpoint, data = null, options = {}) => {
	// Rate limiting check
	if (!securityMonitor.trackApiRequest(endpoint)) {
		throw new Error("Rate limit exceeded. Please try again later.")
	}

	const makeRequest = async () => {
		const requestOptions = {
			method,
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			credentials: "include", // Include httpOnly cookies
			...options,
		}

		// Add body for non-GET requests
		if (data && method !== "GET") {
			requestOptions.body = JSON.stringify(data)
		}

		return fetch(`${BASE_URL}${endpoint}`, requestOptions)
	}

	const response = await makeRequest()
	return handleResponse(response, endpoint, makeRequest)
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
