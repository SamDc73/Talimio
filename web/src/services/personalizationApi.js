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
	const settings = await api.get("/user/settings")

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
	const response = await api.put("/user/settings/instructions", {
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
    // Clear all memories by deleting them one-by-one using the existing endpoint
    // Backend supports DELETE /user/memories/{memory_id} but not a bulk delete endpoint
    // We fetch current memories and delete each to achieve a full clear.
    try {
        const memories = await getUserMemories(_userId, 1000)
        if (!Array.isArray(memories) || memories.length === 0) {
            return { status: "success", message: "No memories to delete" }
        }

        // Delete sequentially to avoid overwhelming the server and to simplify error handling
        let deleted = 0
        for (const m of memories) {
            if (!m?.id) continue
            try {
                await api.delete(`/user/memories/${m.id}`)
                deleted += 1
            } catch (_e) {
                // Continue deleting remaining memories even if one fails
            }
        }

        return { status: "success", message: "Cleared user memories", deleted }
    } catch (e) {
        // Surface an error consistent with other API methods
        throw e
    }
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
