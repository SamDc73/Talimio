/**
 * User ID management utilities for personalization features
 */

/**
 * Get or generate a user ID for the session
 * @returns {string} User ID
 */
export function getUserId() {
	let userId = localStorage.getItem("user_id");

	if (!userId) {
		// Generate a simple user ID for demo purposes
		// In production, this would come from authentication
		userId = `user_${Math.random().toString(36).substr(2, 9)}`;
		localStorage.setItem("user_id", userId);
	}

	return userId;
}

/**
 * Set a custom user ID (for testing or manual override)
 * @param {string} userId - User ID to set
 */
export function setUserId(userId) {
	localStorage.setItem("user_id", userId);
}

/**
 * Clear the stored user ID
 */
export function clearUserId() {
	localStorage.removeItem("user_id");
}

/**
 * Get headers with user ID for API requests
 * @returns {Object} Headers object with x-user-id (only if auth is disabled)
 */
export function getUserHeaders() {
	// When auth is enabled, user identification is handled by auth tokens
	// When auth is disabled, we use a local user ID for personalization
	const authEnabled = import.meta.env.VITE_ENABLE_AUTH === "true";

	if (authEnabled) {
		return {}; // Auth tokens handle user identification
	}

	// In no-auth mode, use local user ID for personalization features
	return {
		"x-user-id": getUserId(),
	};
}
