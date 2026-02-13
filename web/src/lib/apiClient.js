import { API_BASE, joinApiUrl } from "@/lib/apiBase"
import { CSRF_HEADER_NAME, getCsrfHeaders, isCsrfVerificationFailure, SAFE_METHODS } from "@/lib/csrf"
import logger from "@/lib/logger"

// In-flight request cache for deduplication
const inFlightRequests = new Map()

const isFormData = (data) => typeof FormData !== "undefined" && data instanceof FormData

const isBinaryBody = (data) =>
	(typeof Blob !== "undefined" && data instanceof Blob) ||
	(typeof ArrayBuffer !== "undefined" && data instanceof ArrayBuffer)

const parseResponseBody = async (response, responseType) => {
	// FastAPI uses 204 for many mutation endpoints (archive/delete/etc.)
	if (response.status === 204 || response.status === 205) return null

	if (responseType === "response") return response
	if (responseType === "blob") return response.blob()
	if (responseType === "arrayBuffer") return response.arrayBuffer()

	const text = await response.text()
	if (!text) return null
	if (responseType === "text") return text

	const contentType = response.headers.get("content-type") || ""
	const looksLikeJson = contentType.includes("application/json") || contentType.includes("+json")
	return looksLikeJson ? JSON.parse(text) : text
}

const getErrorMessage = (errorData, fallbackMessage) => {
	if (typeof errorData === "string") return errorData
	if (!errorData || typeof errorData !== "object") return fallbackMessage

	const detail = errorData.detail
	if (Array.isArray(detail)) {
		const messages = detail.map((item) => item?.msg).filter(Boolean)
		return messages.join(", ") || fallbackMessage
	}

	if (typeof detail === "string") return detail
	if (typeof errorData.message === "string") return errorData.message
	return fallbackMessage
}

// Helper function to handle API responses
const handleResponse = async (response, endpoint, responseType) => {
	if (!response.ok) {
		let errorData
		try {
			errorData = await parseResponseBody(response, "json")
		} catch (error) {
			logger.error("Failed to parse error response", error, { endpoint, status: response.status })
			errorData = { message: response.statusText }
		}
		if (!errorData) errorData = { message: response.statusText }

		const errorMessage = getErrorMessage(errorData, response.statusText)
		const error = new Error(`API Error: ${response.status} ${errorMessage}`)
		error.status = response.status
		error.data = errorData
		error.headers = response.headers
		throw error
	}

	return parseResponseBody(response, responseType)
}

// Request wrapper with deduplication
const secureRequest = async (method, endpoint, data = null, options = {}) => {
	// Create cache key for deduplication (GET requests only)
	if (method === "GET") {
		// Avoid deduping abortable requests: sharing a promise can couple cancellation across callers.
		if (options?.signal) {
			return executeRequest(method, endpoint, data, options)
		}

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
	const { headers: optionHeaders, responseType, absoluteUrl, ...restOptions } = options

	const makeRequest = async ({ forceRefreshCsrf = false } = {}) => {
		const url = absoluteUrl ? endpoint : joinApiUrl(API_BASE, endpoint)
		const headers = { ...optionHeaders }
		const hasCsrfHeader = Object.keys(headers).some((key) => key.toLowerCase() === CSRF_HEADER_NAME)
		if (!SAFE_METHODS.has(method) && !hasCsrfHeader) {
			Object.assign(headers, await getCsrfHeaders({ forceRefresh: forceRefreshCsrf }))
		}
		const requestOptions = {
			method,
			headers,
			credentials: "include", // Include httpOnly cookies
			cache: method === "GET" ? "no-store" : undefined,
			...restOptions,
		}

		if (data && method !== "GET") {
			if (isFormData(data) || isBinaryBody(data)) {
				requestOptions.body = data
				delete requestOptions.headers["Content-Type"]
				delete requestOptions.headers["content-type"]
			} else if (typeof data === "string") {
				requestOptions.body = data
			} else {
				requestOptions.body = JSON.stringify(data)
				if (!requestOptions.headers["Content-Type"] && !requestOptions.headers["content-type"]) {
					requestOptions.headers["Content-Type"] = "application/json"
				}
			}
		}

		return fetch(url, requestOptions)
	}

	let response = await makeRequest()
	if (!SAFE_METHODS.has(method) && (await isCsrfVerificationFailure(response))) {
		response = await makeRequest({ forceRefreshCsrf: true })
	}
	return handleResponse(response, endpoint, responseType)
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

	// Return the raw Response (useful for streams)
	async raw(endpoint, options = {}) {
		return secureRequest("GET", endpoint, null, { ...options, responseType: "response" })
	},

	async rawPost(endpoint, data = null, options = {}) {
		return secureRequest("POST", endpoint, data, { ...options, responseType: "response" })
	},

	async blob(url, options = {}) {
		return secureRequest("GET", url, null, { ...options, responseType: "blob" })
	},
}
