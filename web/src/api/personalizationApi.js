/**
 * Personalization API service for managing user preferences and AI memory
 */

import { api } from "@/lib/apiClient"

/**
 * Get user personalization settings for current authenticated user
 */
export async function getUserSettings() {
	// Use current user endpoint instead of user-specific endpoint
	const settings = await api.get("/user/settings")

	// Memory count is already included in the settings response
	// No need for separate call

	return settings
}

/**
 * Fetch stored MCP servers for the authenticated user
 */
export async function listMcpServers({ page = 1, pageSize = 50 } = {}) {
	return api.get(`/mcp/servers?page=${page}&pageSize=${pageSize}`)
}

/**
 * Create a new MCP server configuration for the authenticated user
 */
export async function createMcpServer(payload) {
	return api.post("/mcp/servers", payload)
}

/**
 * Delete a stored MCP server configuration
 */
export async function deleteMcpServer(serverId) {
	return api.delete(`/mcp/servers/${serverId}`)
}

/**
 * Update custom AI instructions for current authenticated user
 * @param {string} instructions - The custom instructions to set
 */
export async function updateCustomInstructions(instructions) {
	// Use current user endpoint
	const response = await api.put("/user/settings/instructions", {
		instructions: instructions,
	})
	return response
}

/**
 * List the current user's profile-slot memories.
 * Each item is { id, slot, value, source, updatedAt, lastEvidenceAt?, evidenceText?, sourceMessageId? }.
 * @param {number} limit - Maximum number of memories to fetch (default 100)
 */
export async function getUserMemories(limit = 100) {
	// Use current user endpoint
	const response = await api.get(`/user/memories?limit=${limit}`)
	return response.memories
}

/**
 * Clear all user memories for current authenticated user
 */
export async function clearUserMemories() {
	return api.delete("/user/memories")
}

/**
 * Delete a specific memory for current authenticated user
 * @param {string} memoryId - The memory ID to delete
 */
export async function deleteMemory(memoryId) {
	// Use current user endpoint
	const response = await api.delete(`/user/memories/${memoryId}`)
	return response
}
