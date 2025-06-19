/**
 * API service for personalization and memory management
 */

import { getUserHeaders } from "../utils/userUtils";

const API_BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1";

/**
 * Get user settings including custom instructions and memory count
 * @returns {Promise<Object>} User settings
 */
export async function getUserSettings() {
	try {
		const response = await fetch(`${API_BASE_URL}/user/settings`, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				...getUserHeaders(),
			},
		});

		if (!response.ok) {
			throw new Error(`Failed to get user settings: ${response.statusText}`);
		}

		return await response.json();
	} catch (error) {
		console.error("Error getting user settings:", error);
		throw error;
	}
}

/**
 * Update custom instructions for the user
 * @param {string} instructions - Custom instructions text
 * @returns {Promise<Object>} Update response
 */
export async function updateCustomInstructions(instructions) {
	try {
		const response = await fetch(`${API_BASE_URL}/user/settings/instructions`, {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
				...getUserHeaders(),
			},
			body: JSON.stringify({ instructions }),
		});

		if (!response.ok) {
			throw new Error(`Failed to update instructions: ${response.statusText}`);
		}

		return await response.json();
	} catch (error) {
		console.error("Error updating custom instructions:", error);
		throw error;
	}
}

/**
 * Get custom instructions for the user
 * @returns {Promise<Object>} Custom instructions
 */
export async function getCustomInstructions() {
	try {
		const response = await fetch(`${API_BASE_URL}/user/settings/instructions`, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				...getUserHeaders(),
			},
		});

		if (!response.ok) {
			throw new Error(`Failed to get instructions: ${response.statusText}`);
		}

		return await response.json();
	} catch (error) {
		console.error("Error getting custom instructions:", error);
		throw error;
	}
}

/**
 * Get all user memories
 * @returns {Promise<Array>} List of user memories
 */
export async function getUserMemories() {
	try {
		const response = await fetch(`${API_BASE_URL}/user/memories`, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				...getUserHeaders(),
			},
		});

		if (!response.ok) {
			throw new Error(`Failed to get memories: ${response.statusText}`);
		}

		return await response.json();
	} catch (error) {
		console.error("Error getting user memories:", error);
		throw error;
	}
}

/**
 * Clear all user memories
 * @returns {Promise<Object>} Clear response
 */
export async function clearUserMemory() {
	try {
		const response = await fetch(`${API_BASE_URL}/user/memory`, {
			method: "DELETE",
			headers: {
				"Content-Type": "application/json",
				...getUserHeaders(),
			},
		});

		if (!response.ok) {
			throw new Error(`Failed to clear memory: ${response.statusText}`);
		}

		return await response.json();
	} catch (error) {
		console.error("Error clearing user memory:", error);
		throw error;
	}
}
