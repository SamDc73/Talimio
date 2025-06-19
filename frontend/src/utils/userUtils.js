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
 * @returns {Object} Headers object with x-user-id (only if not in self-hosting mode)
 */
export function getUserHeaders() {
	// In self-hosting mode, don't send user ID header so backend uses its default
	const isSelfHosting = import.meta.env.VITE_AUTH_DISABLED === 'true' || 
						  import.meta.env.VITE_SELF_HOSTING === 'true';
	
	if (isSelfHosting) {
		return {}; // No user header, let backend use default
	}
	
	return {
		"x-user-id": getUserId(),
	};
}
