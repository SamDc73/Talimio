import { useApi } from "../hooks/useApi";
import { getUserHeaders } from "../utils/userUtils";
import useAppStore from "../stores/useAppStore";

export const assistantApi = {
	async chat(message, conversationHistory = [], stream = false) {
		// Get user's preferred model from store
		const assistantModel = useAppStore.getState().preferences.assistantModel;
		
		const response = await fetch(
			`${import.meta.env.VITE_API_BASE || "/api/v1"}/assistant/chat`,
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					...getUserHeaders(),
				},
				body: JSON.stringify({
					message,
					conversation_history: conversationHistory,
					user_id: getUserHeaders()["x-user-id"] || null,
					model: assistantModel, // Include preferred model
					stream, // Enable streaming if requested
				}),
			},
		);

		if (!response.ok) {
			throw new Error("Failed to send message");
		}

		// Handle streaming response
		if (stream) {
			return response; // Return the response object for streaming
		}

		return response.json();
	},

	async *chatStream(message, conversationHistory = []) {
		const response = await this.chat(message, conversationHistory, true);
		
		if (!response.body) {
			throw new Error("No response body for streaming");
		}

		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";

		try {
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				
				// Process all complete lines
				for (let i = 0; i < lines.length - 1; i++) {
					const line = lines[i].trim();
					if (line.startsWith("data: ")) {
						const data = line.slice(6);
						if (data === "[DONE]") {
							return;
						}
						try {
							const parsed = JSON.parse(data);
							yield parsed;
						} catch (e) {
							console.error("Failed to parse SSE data:", e);
						}
					}
				}
				
				// Keep the last incomplete line in the buffer
				buffer = lines[lines.length - 1];
			}
		} finally {
			reader.releaseLock();
		}
	},

	async getAvailableModels() {
		const response = await fetch(
			`${import.meta.env.VITE_API_BASE || "/api/v1"}/assistant/models`,
			{
				method: "GET",
				headers: {
					"Content-Type": "application/json",
					...getUserHeaders(),
				},
			},
		);

		if (!response.ok) {
			throw new Error("Failed to fetch available models");
		}

		return response.json();
	},
};

export function useAssistantChat() {
	const { execute, loading, error } = useApi();

	const sendMessage = async (message, conversationHistory = []) => {
		return execute(async () => {
			return assistantApi.chat(message, conversationHistory);
		});
	};

	const sendStreamingMessage = async (message, conversationHistory = [], onChunk) => {
		try {
			const stream = assistantApi.chatStream(message, conversationHistory);
			let fullResponse = "";

			for await (const chunk of stream) {
				if (chunk.content) {
					fullResponse += chunk.content;
					onChunk(chunk.content, fullResponse);
				}
			}

			return { response: fullResponse };
		} catch (err) {
			console.error("Streaming error:", err);
			throw err;
		}
	};

	const getAvailableModels = async () => {
		return execute(async () => {
			return assistantApi.getAvailableModels();
		});
	};

	return {
		sendMessage,
		sendStreamingMessage,
		getAvailableModels,
		loading,
		error,
	};
}
