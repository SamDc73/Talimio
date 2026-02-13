const CSRF_COOKIE_NAME = "csrftoken"
export const CSRF_HEADER_NAME = "x-csrftoken"
export const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"])

const CSRF_REFRESH_ENDPOINT = "/api/v1/auth/options"
const CSRF_FAILURE_TEXT = "csrf token verification failed"

let csrfRefreshPromise = null

export const getCookieValue = (cookieName) => {
	if (typeof document === "undefined" || !document.cookie) return null
	const encodedKey = `${encodeURIComponent(cookieName)}=`
	const cookiePair = document.cookie.split("; ").find((item) => item.startsWith(encodedKey))
	if (!cookiePair) return null
	return decodeURIComponent(cookiePair.slice(encodedKey.length))
}

export const getCsrfToken = () => getCookieValue(CSRF_COOKIE_NAME)

export const refreshCsrfToken = async () => {
	if (typeof window === "undefined") return null

	if (!csrfRefreshPromise) {
		csrfRefreshPromise = fetch(CSRF_REFRESH_ENDPOINT, {
			method: "GET",
			credentials: "include",
			cache: "no-store",
		})
			.catch(() => null)
			.finally(() => {
				csrfRefreshPromise = null
			})
	}

	await csrfRefreshPromise
	return getCsrfToken()
}

export const ensureCsrfToken = async ({ forceRefresh = false } = {}) => {
	const existing = getCsrfToken()
	if (existing && !forceRefresh) return existing
	return refreshCsrfToken()
}

export const isCsrfVerificationFailure = async (response) => {
	if (!response || response.status !== 403) return false

	try {
		const contentType = response.headers.get("content-type") || ""

		if (contentType.includes("application/json")) {
			const payload = await response.clone().json()
			const detail = payload?.detail
			return typeof detail === "string" && detail.toLowerCase().includes(CSRF_FAILURE_TEXT)
		}

		const text = await response.clone().text()
		return text.toLowerCase().includes(CSRF_FAILURE_TEXT)
	} catch {
		return false
	}
}
