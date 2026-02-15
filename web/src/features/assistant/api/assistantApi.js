import { api } from "@/lib/apiClient"

const DEFAULT_CONVERSATIONS_PAGE = 1
const DEFAULT_CONVERSATIONS_LIMIT = 20

const toQueryString = (params) => {
	const query = new URLSearchParams()
	for (const [key, value] of Object.entries(params)) {
		if (value === undefined || value === null) {
			continue
		}
		query.set(key, String(value))
	}
	return query.toString()
}

// Assistant API service - centralized API calls for the assistant feature
export const assistantApi = {
	async getAvailableModels() {
		return api.get("/assistant/models")
	},

	async listConversations({ page = DEFAULT_CONVERSATIONS_PAGE, limit = DEFAULT_CONVERSATIONS_LIMIT } = {}) {
		const query = toQueryString({ page, limit })
		return api.get(`/assistant/conversations?${query}`)
	},

	async createConversation(payload = {}) {
		return api.post("/assistant/conversations", payload)
	},

	async getConversation(conversationId) {
		return api.get(`/assistant/conversations/${conversationId}`)
	},

	async renameConversation(conversationId, title) {
		return api.patch(`/assistant/conversations/${conversationId}`, { title })
	},

	async deleteConversation(conversationId) {
		return api.delete(`/assistant/conversations/${conversationId}`)
	},

	async getConversationHistory(conversationId) {
		return api.get(`/assistant/conversations/${conversationId}/history`)
	},

	async appendConversationHistory(conversationId, item) {
		return api.post(`/assistant/conversations/${conversationId}/history`, item)
	},
}
