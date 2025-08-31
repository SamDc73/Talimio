/**
 * Centralized logger using Vite best practices with import.meta.env.DEV
 * Tree-shakeable in production builds when import.meta.env.DEV is false
 */

// Vite built-in DEV flag - automatically true in development, false in production
const isDev = import.meta.env.DEV

// Store console methods in a separate object to avoid linter issues
const nativeConsole = globalThis.console

/**
 * Logger that's optimized for tree-shaking in production
 * Functions are empty in production, allowing Vite to remove them entirely
 */
const logger = {
	log: isDev ? (...args) => nativeConsole.log("[LOG]", ...args) : () => {},
	error: isDev ? (...args) => nativeConsole.error("[ERROR]", ...args) : () => {},
	warn: isDev ? (...args) => nativeConsole.warn("[WARN]", ...args) : () => {},
	info: isDev ? (...args) => nativeConsole.info("[INFO]", ...args) : () => {},
	debug: isDev ? (...args) => nativeConsole.debug("[DEBUG]", ...args) : () => {},
	table: isDev ? (data) => nativeConsole.table(data) : () => {},
	time: isDev ? (label) => nativeConsole.time(label) : () => {},
	timeEnd: isDev ? (label) => nativeConsole.timeEnd(label) : () => {},
	group: isDev ? (label) => nativeConsole.group(label) : () => {},
	groupEnd: isDev ? () => nativeConsole.groupEnd() : () => {},
	groupCollapsed: isDev ? (label) => nativeConsole.groupCollapsed(label) : () => {},

	// Performance monitoring helper
	measure: isDev
		? (name, fn) => {
				const start = performance.now()
				const result = fn()
				const end = performance.now()
				nativeConsole.log(`[PERF] ${name}: ${(end - start).toFixed(2)}ms`)
				return result
			}
		: (_, fn) => fn(),

	// Assert helper for development
	assert: isDev ? (condition, message) => nativeConsole.assert(condition, message) : () => {},
}

export default logger
