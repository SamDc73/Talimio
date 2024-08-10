/**
 * Authentication testing utilities
 * Run these in the browser console to test auth flow
 */

// Test auth state
export const testAuthState = () => {
	const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true"
	const token = localStorage.getItem("access_token")

	return {
		authEnabled,
		hasToken: !!token,
		currentPath: window.location.pathname,
	}
}

// Clear all auth data
export const clearAuthData = () => {
	localStorage.removeItem("access_token")
	localStorage.removeItem("app-storage") // Clear Zustand store
}

// Simulate auth bypass attempt
export const simulateAuthBypass = () => {
	// Try to access protected route directly
	window.history.pushState({}, "", "/courses")

	// This should trigger protection mechanisms
	setTimeout(() => {}, 1000)
}

// Check if auth protection is working
export const checkAuthProtection = () => {
	const protectedPaths = ["/courses", "/books", "/videos", "/roadmap"]
	const currentPath = window.location.pathname
	const isOnProtectedPath = protectedPaths.some((path) => currentPath.startsWith(path))

	const authState = testAuthState()

	if (isOnProtectedPath && authState.authEnabled && !authState.hasToken) {
		return false
	}
	return true
}

// Make functions available globally for console testing
if (typeof window !== "undefined") {
	window.authTest = {
		testAuthState,
		clearAuthData,
		simulateAuthBypass,
		checkAuthProtection,
	}
}
