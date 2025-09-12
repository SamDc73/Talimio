/**
 * Streamlined Logger Service for Vite 7
 * Leverages Vite's build-time optimization for zero runtime overhead in dev
 *
 * In development: Logs to console with nice formatting
 * In production: Sends to logging endpoint (when configured)
 */

class LoggerService {
	constructor() {
		// Only initialize in production when endpoint is configured
		if (import.meta.env.PROD && import.meta.env.VITE_TELEMETRY_ENDPOINT) {
			this.endpoint = import.meta.env.VITE_TELEMETRY_ENDPOINT
		}

		// Add Vite 7's preload error handler in production
		if (import.meta.env.PROD) {
			this.setupErrorHandlers()
		}
	}

	/**
	 * Setup global error handlers for production
	 */
	setupErrorHandlers() {
		// Handle Vite dynamic import failures
		window.addEventListener("vite:preloadError", (_event) => {
			// Optionally reload page for critical failures
			// window.location.reload()
		})

		// Catch unhandled errors
		window.addEventListener("error", (event) => {
			this.error("Unhandled error", event.error, {
				message: event.message,
				filename: event.filename,
				lineno: event.lineno,
				colno: event.colno,
			})
		})

		// Catch unhandled promise rejections
		window.addEventListener("unhandledrejection", (event) => {
			this.error("Unhandled promise rejection", event.reason)
		})
	}

	/**
	 * Send data to endpoint or console
	 */
	async send(data) {
		// In dev, just log to console with nice formatting
		if (import.meta.env.DEV) {
			const _style = this.getConsoleStyle(data.type)
			return
		}

		// In production, send to endpoint if configured
		if (!this.endpoint) return

		try {
			// Fire and forget - don't await to avoid blocking
			fetch(this.endpoint, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					...data,
					timestamp: new Date().toISOString(),
					url: window.location.href,
					userAgent: navigator.userAgent,
				}),
				// Use keepalive for reliability
				keepalive: true,
			})
		} catch {
			// Silent fail in production
		}
	}

	/**
	 * Get console styling based on log type
	 */
	getConsoleStyle(type) {
		const styles = {
			track: "color: #00d4ff; font-weight: bold;",
			error: "color: #ff5555; font-weight: bold;",
			info: "color: #00d4ff; font-weight: bold;",
			timing: "color: #ffff00; font-weight: bold;",
		}
		return styles[type] || styles.info
	}

	/**
	 * Track user events
	 */
	track(event, data = {}) {
		this.send({ type: "track", event, data })
	}

	/**
	 * Log errors with context
	 */
	error(message, error, context = {}) {
		const errorData = {
			type: "error",
			message,
			error: error
				? {
						message: error?.message,
						stack: error?.stack,
						name: error?.name,
					}
				: null,
			context,
		}

		// In dev, also use console.error for better stack traces
		if (import.meta.env.DEV) {
		} else {
			this.send(errorData)
		}
	}

	/**
	 * Log informational messages
	 */
	info(message, data = {}) {
		this.send({ type: "info", message, data })
	}

	/**
	 * Performance timing
	 */
	timing(metric, value, tags = {}) {
		this.send({ type: "timing", metric, value, tags })
	}

	/**
	 * Measure async operation duration
	 */
	async measure(name, operation) {
		const start = performance.now()
		try {
			const result = await operation()
			const duration = Math.round(performance.now() - start)
			this.timing(name, duration, { status: "success" })
			return result
		} catch (error) {
			const duration = Math.round(performance.now() - start)
			this.timing(name, duration, { status: "error" })
			throw error
		}
	}
}

// Create singleton instance
const logger = new LoggerService()

// Export for use in components
export default logger

// Also attach to window for global access (useful for error boundaries)
if (typeof window !== "undefined") {
	window.logger = logger
}
