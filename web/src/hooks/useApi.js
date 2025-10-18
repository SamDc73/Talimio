import { useRef, useState } from "react"

const BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

// Helper function to construct the full URL
const buildUrl = (endpoint, pathParams) => {
	let url = `${BASE_URL}${endpoint}`
	if (pathParams) {
		for (const key of Object.keys(pathParams)) {
			url = url.replace(`{${key}}`, encodeURIComponent(pathParams[key]))
		}
	}
	return url
}

// Helper function to prepare request options
const prepareRequestOptions = (method, body, customOptions) => {
	const { headers, ...restOfCustomOptions } = customOptions

	const options = {
		method,
		headers: {
			"Content-Type": "application/json",
			...headers,
		},
		// Always include cookies for auth-protected endpoints
		credentials: "include",
		...restOfCustomOptions,
	}

	// Only add body if method allows and body is provided
	if (body && !["GET", "HEAD"].includes(method.toUpperCase())) {
		options.body = JSON.stringify(body)
	}

	return options
}

// Helper function to handle the API response
const handleResponse = async (response) => {
	if (!response.ok) {
		let errorData
		try {
			errorData = await response.json()
		} catch (_e) {
			errorData = { message: response.statusText }
		}
		const error = new Error(`API Error: ${response.status} ${errorData?.message || response.statusText}`)
		error.status = response.status
		error.data = errorData
		throw error
	}

	if (response.status === 204 || response.headers.get("content-length") === "0") {
		return null
	}

	return response.json()
}

export function useApi(endpoint, options = {}) {
	const [data, setData] = useState(null)
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)
	const abortControllerRef = useRef(null)

	const execute = async (body = null, callOptions = {}) => {
		const combinedOptions = { ...options, ...callOptions }
		const { method = "GET", pathParams, queryParams, ...fetchOptions } = combinedOptions

		if (abortControllerRef.current) {
			abortControllerRef.current.abort()
		}
		abortControllerRef.current = new AbortController()

		setIsLoading(true)
		setError(null)
		setData(null)

		let url = buildUrl(endpoint, pathParams)
		if (queryParams && Object.keys(queryParams).length > 0) {
			const qs = new URLSearchParams(queryParams).toString()
			url += (url.includes("?") ? "&" : "?") + qs
		}

		try {
			const requestOptions = prepareRequestOptions(method, body, {
				...fetchOptions,
				signal: abortControllerRef.current.signal,
			})
			const response = await fetch(url, requestOptions)
			const responseData = await handleResponse(response)
			setData(responseData)
			return responseData
		} catch (err) {
			if (err.name === "AbortError") {
				return
			}
			setError(err)
			throw err
		} finally {
			setIsLoading(false)
			abortControllerRef.current = null
		}
	}

	return { data, isLoading, error, execute }
}
