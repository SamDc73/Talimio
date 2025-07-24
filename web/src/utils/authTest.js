/**
 * Authentication testing utilities
 * Run these in the browser console to test auth flow
 */

// Test auth state
export const testAuthState = () => {
	console.log("🧪 Testing auth state...");

	const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";
	const token = localStorage.getItem("access_token");

	console.log("Auth enabled:", authEnabled);
	console.log("Token exists:", !!token);
	console.log("Token:", token ? `${token.slice(0, 20)}...` : "none");
	console.log("Current path:", window.location.pathname);

	return {
		authEnabled,
		hasToken: !!token,
		currentPath: window.location.pathname,
	};
};

// Clear all auth data
export const clearAuthData = () => {
	console.log("🧹 Clearing all auth data...");

	localStorage.removeItem("access_token");
	localStorage.removeItem("app-storage"); // Clear Zustand store

	console.log("✅ Auth data cleared. Reload page to see effect.");
};

// Simulate auth bypass attempt
export const simulateAuthBypass = () => {
	console.log("🚨 Simulating auth bypass attempt...");

	// Try to access protected route directly
	window.history.pushState({}, "", "/courses");
	console.log("Attempted direct navigation to /courses");

	// This should trigger protection mechanisms
	setTimeout(() => {
		console.log("Current path after bypass attempt:", window.location.pathname);
	}, 1000);
};

// Check if auth protection is working
export const checkAuthProtection = () => {
	console.log("🔍 Checking auth protection status...");

	const protectedPaths = ["/courses", "/books", "/videos", "/roadmap"];
	const currentPath = window.location.pathname;
	const isOnProtectedPath = protectedPaths.some((path) =>
		currentPath.startsWith(path),
	);

	const authState = testAuthState();

	console.log("On protected path:", isOnProtectedPath);
	console.log(
		"Should be protected:",
		authState.authEnabled && !authState.hasToken,
	);

	if (isOnProtectedPath && authState.authEnabled && !authState.hasToken) {
		console.log("🚨 AUTH VIOLATION DETECTED: On protected path without token!");
		return false;
	}

	console.log("✅ Auth protection working correctly");
	return true;
};

// Make functions available globally for console testing
if (typeof window !== "undefined") {
	window.authTest = {
		testAuthState,
		clearAuthData,
		simulateAuthBypass,
		checkAuthProtection,
	};

	console.log("🧪 Auth test utilities loaded. Use window.authTest in console.");
}
