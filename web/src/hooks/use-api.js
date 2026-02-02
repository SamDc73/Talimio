import { useRef, useState } from "react"
import { api } from "@/lib/apiClient"

const buildEndpoint = (endpoint, pathParams) => {
	let url = endpoint
	if (pathParams) {
		for (const key of Object.keys(pathParams)) {
			url = url.replace(`{${key}}`, encodeURIComponent(pathParams[key]))
		}
	}
	return url
}

const executeApiRequest = async (method, endpoint, body, requestOptions) => {
	const normalizedMethod = method.toUpperCase()

	switch (normalizedMethod) {
		case "GET": {
			return api.get(endpoint, requestOptions)
		}
		case "POST": {
			return api.post(endpoint, body, requestOptions)
		}
		case "PUT": {
			return api.put(endpoint, body, requestOptions)
		}
		case "PATCH": {
			return api.patch(endpoint, body, requestOptions)
		}
		case "DELETE": {
			return api.delete(endpoint, requestOptions)
		}
		default: {
			throw new Error(`Unsupported method: ${method}`)
		}
	}
}

export function useApi(endpoint, options = {}) {
	const [data, setData] = useState(null)
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)
	const abortControllerRef = useRef(null)
	const requestIdRef = useRef(0)

	const execute = async (body = null, callOptions = {}) => {
		const myId = ++requestIdRef.current
		const combinedOptions = { ...options, ...callOptions }
		const { method = "GET", pathParams, queryParams, ...fetchOptions } = combinedOptions

		if (abortControllerRef.current) {
			abortControllerRef.current.abort()
		}
		abortControllerRef.current = new AbortController()

		setIsLoading(true)
		setError(null)
		setData(null)

		let requestEndpoint = buildEndpoint(endpoint, pathParams)
		if (queryParams && Object.keys(queryParams).length > 0) {
			const qs = new URLSearchParams(queryParams).toString()
			requestEndpoint += (requestEndpoint.includes("?") ? "&" : "?") + qs
		}

		try {
			const responseData = await executeApiRequest(method, requestEndpoint, body, {
				...fetchOptions,
				signal: abortControllerRef.current.signal,
			})
			// Only the latest request updates state
			if (requestIdRef.current === myId) {
				setData(responseData)
			}
			return responseData
		} catch (err) {
			if (err.name === "AbortError") {
				return
			}
			if (requestIdRef.current === myId) {
				setError(err)
			}
			throw err
		} finally {
			if (requestIdRef.current === myId) {
				setIsLoading(false)
			}
			abortControllerRef.current = null
		}
	}

	return { data, isLoading, error, execute }
}
