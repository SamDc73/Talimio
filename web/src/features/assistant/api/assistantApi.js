import { api } from "@/lib/apiClient"

// Assistant API service - centralized API calls for the assistant feature
export const assistantApi = {
	async getAvailableModels() {
		return api.get("/assistant/models")
	},
	async createChatStream(body, abortSignal) {
		return api.rawPost("/assistant/chat", body, {
			headers: { Accept: "text/event-stream" },
			signal: abortSignal,
		})
	},
}
