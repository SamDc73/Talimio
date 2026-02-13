import { api } from "@/lib/apiClient"

// Assistant API service - centralized API calls for the assistant feature
export const assistantApi = {
	async getAvailableModels() {
		return api.get("/assistant/models")
	},
}
