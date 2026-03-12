import { faro, frontendReleaseVersion } from "@/lib/faro"

class LoggerService {
	errorHandlersInstalled = false

	installGlobalErrorHandlers() {
		if (this.errorHandlersInstalled || typeof window === "undefined") {
			return
		}

		window.addEventListener("vite:preloadError", (event) => {
			this.error("Vite preload error", event?.payload ?? event?.error ?? null, {
				type: "vite:preloadError",
			})
		})

		this.errorHandlersInstalled = true
	}

	send(data) {
		const sentToFaro = this.pushToFaro(data)
		if (import.meta.env.DEV || !sentToFaro) {
			this.logToConsole(data)
		}
	}

	pushToFaro(data) {
		if (!faro?.api) {
			return false
		}

		const context = {
			release: frontendReleaseVersion,
			url: window.location.href,
			...data.context,
		}
		if (data.data && typeof data.data === "object") {
			context.data = data.data
		}
		if (data.tags && typeof data.tags === "object") {
			context.tags = data.tags
		}

		try {
			switch (data.type) {
				case "error": {
					const error =
						data.error?.name || data.error?.message
							? Object.assign(new Error(data.error?.message || data.message), {
									name: data.error?.name || "Error",
									stack: data.error?.stack,
								})
							: new Error(data.message)
					faro.api.pushError(error, {
						type: data.context?.type || "handled_error",
						context,
					})
					break
				}
				case "track": {
					faro.api.pushEvent(data.event, context)
					break
				}
				case "timing": {
					faro.api.pushMeasurement({
						type: data.metric,
						values: {
							value: data.value,
						},
						context,
					})
					break
				}
				default: {
					faro.api.pushLog([data.message || data.event || "frontend_log"], {
						level: data.type || "info",
						context,
					})
				}
			}
			return true
		} catch (error) {
			if (import.meta.env.DEV) {
				// biome-ignore lint/suspicious/noConsole: Explicit observability fallback in development
				console.warn("Failed to push frontend log to Faro", error)
			}
			return false
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

	track(event, data = {}) {
		this.send({ type: "track", event, data })
	}

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

	info(message, data = {}) {
		this.send({ type: "info", message, data })
	}

	warn(message, data = {}) {
		this.send({ type: "warn", message, data })
	}

	timing(metric, value, tags = {}) {
		this.send({ type: "timing", metric, value, tags })
	}
}

const logger = new LoggerService()

export default logger
