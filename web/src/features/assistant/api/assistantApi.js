// Assistant API service - centralized API calls for the assistant feature
export const assistantApi = {
	async getAvailableModels() {
		const base = import.meta.env.VITE_API_BASE || "/api/v1"
		const response = await fetch(`${base}/assistant/models`, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
			},
			// Ensure auth cookies/session are included for protected endpoint
			credentials: "include",
		})

		if (!response.ok) {
			throw new Error("Failed to fetch available models")
		}

		return response.json()
	},
	async createChatStream(body, abortSignal) {
		const base = import.meta.env.VITE_API_BASE || "/api/v1"
		const response = await fetch(`${base}/assistant/chat`, {
			method: "POST",
			headers: {
				Accept: "text/event-stream",
				"Content-Type": "application/json",
			},
			body: JSON.stringify(body),
			signal: abortSignal,
			credentials: "include",
		})

		if (!response.ok) {
			const text = await response.text().catch(() => "")
			throw new Error(text || "Failed to start assistant chat stream")
		}

		return response
	},
}
