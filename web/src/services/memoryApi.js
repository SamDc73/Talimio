/**
 * Minimal memory API service - SECURE VERSION
 * Uses /user/ endpoints that automatically validate the authenticated user
 */

const API_BASE_URL = import.meta.env.VITE_API_URL

/**
 * Get all memories for the current authenticated user
 * Note: userId parameter kept for backward compatibility but not used
 */
export async function getMemories(_userId, limit = 50) {
	// SECURE: Uses /user/memories which validates authenticated user
	const response = await fetch(`${API_BASE_URL}/user/memories?limit=${limit}`, {
		credentials: "include",
	})
	if (!response.ok) throw new Error("Failed to fetch memories")
	return response.json()
}

/**
 * Delete a specific memory for the current authenticated user
 * Note: userId parameter kept for backward compatibility but not used
 */
export async function deleteMemory(_userId, memoryId) {
	// SECURE: Uses /user/memories/{id} which validates authenticated user
	const response = await fetch(`${API_BASE_URL}/user/memories/${memoryId}`, {
		method: "DELETE",
		credentials: "include",
	})
	if (!response.ok) throw new Error("Failed to delete memory")
	return response.json()
}

// That's it! No search, no clear all, no toggle - MINIMAL MVP
