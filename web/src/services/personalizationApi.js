/**
 * API service for personalization and memory management
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

/**
 * Get user settings including custom instructions and memory count
 * @returns {Promise<Object>} User settings
 */
export async function getUserSettings() {
	const response = await fetch(`${API_BASE_URL}/user/settings`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
		},
	})

	if (!response.ok) {
		throw new Error(`Failed to get user settings: ${response.statusText}`)
	}

	return await response.json()
}

/**
 * Update custom instructions for the user
 * @param {string} instructions - Custom instructions text
 * @returns {Promise<Object>} Update response
 */
export async function updateCustomInstructions(instructions) {
	const response = await fetch(`${API_BASE_URL}/user/settings/instructions`, {
		method: "PUT",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ instructions }),
	})

	if (!response.ok) {
		throw new Error(`Failed to update instructions: ${response.statusText}`)
	}

	return await response.json()
}

/**
 * Get custom instructions for the user
 * @returns {Promise<Object>} Custom instructions
 */
export async function getCustomInstructions() {
	const response = await fetch(`${API_BASE_URL}/user/settings/instructions`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
		},
	})

	if (!response.ok) {
		throw new Error(`Failed to get instructions: ${response.statusText}`)
	}

	return await response.json()
}

/**
 * Get all user memories
 * @returns {Promise<Array>} List of user memories
 */
export async function getUserMemories() {
	const response = await fetch(`${API_BASE_URL}/user/memories`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
		},
	})

	if (!response.ok) {
		throw new Error(`Failed to get memories: ${response.statusText}`)
	}

	return await response.json()
}

/**
 * Clear all user memories
 * @returns {Promise<Object>} Clear response
 */
export async function clearUserMemory() {
	const response = await fetch(`${API_BASE_URL}/user/memory`, {
		method: "DELETE",
		headers: {
			"Content-Type": "application/json",
		},
	})

	if (!response.ok) {
		throw new Error(`Failed to clear memory: ${response.statusText}`)
	}

	return await response.json()
}
