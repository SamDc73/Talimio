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
		window.addEventListener("vite:preloadError", (event) => {
			this.error("Vite preload error", event?.payload ?? event?.error ?? null, {
				type: "vite:preloadError",
			})
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
		if (import.meta.env.DEV) {
			this.logToConsole(data)
			return
		}

		if (!this.endpoint) {
			if (!this.hasReportedMissingEndpoint) {
				// biome-ignore lint/suspicious/noConsole: Explicit production diagnostics when telemetry endpoint is missing
				console.warn("[WARN] Telemetry endpoint is not configured. Falling back to console logging.")
				this.hasReportedMissingEndpoint = true
			}
			this.logToConsole(data)
			return
		}

		try {
			const payload = {
				...data,
				timestamp: new Date().toISOString(),
				url: window.location.href,
				userAgent: navigator.userAgent,
			}
			// Fire and forget - don't await to avoid blocking
			fetch(this.endpoint, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(payload),
				// Use keepalive for reliability
				keepalive: true,
			}).catch((error) => {
				// biome-ignore lint/suspicious/noConsole: Explicit diagnostics for telemetry failures in production
				console.error("[ERROR] Failed to send telemetry log", { error, payload })
			})
		} catch (error) {
			// biome-ignore lint/suspicious/noConsole: Explicit diagnostics for telemetry setup failures in production
			console.error("[ERROR] Failed to initialize telemetry log request", { error, data })
			this.logToConsole(data)
		}
	}

	logToConsole(data) {
		const message = `[${String(data.type || "info").toUpperCase()}] ${data.event || data.message || ""}`
		const payload = data.data || data
		switch (data.type) {
			case "error": {
				// biome-ignore lint/suspicious/noConsole: Development/fallback logging
				console.error(message, payload)
				break
			}
			case "warn": {
				// biome-ignore lint/suspicious/noConsole: Development/fallback logging
				console.warn(message, payload)
				break
			}
			case "info": {
				// biome-ignore lint/suspicious/noConsole: Development/fallback logging
				console.info(message, payload)
				break
			}
			default: {
				// biome-ignore lint/suspicious/noConsole: Development/fallback logging
				console.log(message, payload)
			}
		}
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

		this.send(errorData)
	}

	/**
	 * Log informational messages
	 */
	info(message, data = {}) {
		this.send({ type: "info", message, data })
	}

	/**
	 * Log warnings
	 */
	warn(message, data = {}) {
		this.send({ type: "warn", message, data })
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
	endpoint = null
	hasReportedMissingEndpoint = false
}

// Create singleton instance
const logger = new LoggerService()

// Export for use in components
export default logger

// Also attach to window for global access (useful for error boundaries)
if (typeof window !== "undefined") {
	window.logger = logger
}
