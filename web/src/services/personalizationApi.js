/**
 * Personalization API service for managing user preferences and AI memory
 */

import { api } from "@/lib/apiClient"

/**
 * Get user personalization settings
 */
export async function getUserSettings() {
	try {
		const response = await api.get("/user/settings")
		return response.data
	} catch (error) {
		console.error("Failed to fetch user settings:", error)
		throw error
	}
}

/**
 * Update custom AI instructions
 */
export async function updateCustomInstructions(instructions) {
	try {
		const response = await api.patch("/user/settings", {
			custom_instructions: instructions,
		})
		return response.data
	} catch (error) {
		console.error("Failed to update custom instructions:", error)
		throw error
	}
}

/**
 * Get user memories from the AI system
 */
export async function getUserMemories() {
	try {
		const response = await api.get("/memory/user")
		return response.data.memories || []
	} catch (error) {
		console.error("Failed to fetch user memories:", error)
		throw error
	}
}

/**
 * Clear all user memories
 */
export async function clearUserMemory() {
	try {
		const response = await api.delete("/memory/clear")
		return response.data
	} catch (error) {
		console.error("Failed to clear user memory:", error)
		throw error
	}
}