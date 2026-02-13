export const DEFAULT_API_BASE = "/api/v1"
export const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API_BASE

export const joinApiUrl = (baseUrl, endpoint) => {
	if (baseUrl.endsWith("/") && endpoint.startsWith("/")) return `${baseUrl.slice(0, -1)}${endpoint}`
	if (!baseUrl.endsWith("/") && !endpoint.startsWith("/")) return `${baseUrl}/${endpoint}`
	return `${baseUrl}${endpoint}`
}

export const getApiUrl = (endpoint) => joinApiUrl(API_BASE, endpoint)
