/**
 * Debug utilities loader
 * Conditionally loads debug-only tools when import.meta.env.DEV is true
 */

import logger from "./logger.js"

/**
 * Dynamically load debug tools only in development
 * Returns null in production for tree-shaking
 */
export async function loadDebugTools() {
	if (import.meta.env.DEV) {
		try {
			// Dynamically import auth test utilities
			const { default: authTest } = await import("./authTest.js")
			logger.log("[DEBUG] Debug tools loaded successfully")
			return {
				authTest,
				// Add other debug tools here as needed
			}
		} catch (error) {
			logger.error("[DEBUG] Failed to load debug tools:", error)
			return null
		}
	}
	return null
}

/**
 * Helper to run code only in development
 */
export function runInDev(callback) {
	if (import.meta.env.DEV) {
		return callback()
	}
}

/**
 * Debug flag for conditional logic
 */
export const isDebugMode = import.meta.env.DEV
