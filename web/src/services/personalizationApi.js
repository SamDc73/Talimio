/**
 * Personalization API service for managing user preferences and AI memory
 */

import { api } from "@/lib/apiClient"

/**
 * Get user personalization settings
 * @param {string} userId - The user ID to fetch settings for
 */
export async function getUserSettings(_userId) {
	// Use current user endpoint instead of user-specific endpoint
	const settings = await api.get(`/user/settings`)

	// Memory count is already included in the settings response
	// No need for separate call

	return settings
}

/**
 * Update custom AI instructions
 * @param {string} userId - The user ID
 * @param {string} instructions - The custom instructions to set
 */
export async function updateCustomInstructions(_userId, instructions) {
	// Use current user endpoint
	const response = await api.put(`/user/settings/instructions`, {
		instructions: instructions,
	})
	return response
}

/**
 * Get user memories from the AI system
 * @param {string} userId - The user ID
 * @param {number} limit - Maximum number of memories to fetch
 */
export async function getUserMemories(_userId, limit = 50) {
	// Use current user endpoint
	const response = await api.get(`/user/memories?limit=${limit}`)
	return response.memories || []
}

/**
 * Clear all user memories (deletes one by one - MVP approach)
 * @param {string} userId - The user ID
 */
export async function clearUserMemory(_userId) {
	// Use current user endpoint to clear memories (note: singular 'memory' in endpoint)
	const response = await api.delete(`/user/memory`)
	return response
}

/**
 * Delete a specific memory
 * @param {string} userId - The user ID
 * @param {string} memoryId - The memory ID to delete
 */
export async function deleteMemory(_userId, memoryId) {
	// Use current user endpoint
	const response = await api.delete(`/user/memories/${memoryId}`)
	return response
}
