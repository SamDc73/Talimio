import { useApi } from "../hooks/useApi";
import useAppStore from "../stores/useAppStore";

export const assistantApi = {
	async chat(
		message,
		conversationHistory = [],
		stream = false,
		contextData = null,
	) {
		// Get user's preferred model from store
		const assistantModel = useAppStore.getState().preferences.assistantModel;

		const requestBody = {
			message,
			conversation_history: conversationHistory,
			user_id: null, // User ID is handled by auth headers
			model: assistantModel, // Include preferred model
			stream, // Enable streaming if requested
		};

		// Add context data if provided
		if (contextData) {
			requestBody.context_type = contextData.contextType;
			// Ensure context_id is a string (in case it's passed as an object)
			requestBody.context_id = String(contextData.contextId);
			requestBody.context_meta = contextData.contextMeta;

			// Debug logging for context
			console.log("[AssistantAPI] Sending request with context:", {
				type: contextData.contextType,
				id: contextData.contextId,
				meta: contextData.contextMeta,
			});
		} else {
			console.log("[AssistantAPI] No context provided for this request");
		}

		const response = await fetch(
			`${import.meta.env.VITE_API_BASE || "/api/v1"}/assistant/chat`,
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(requestBody),
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

	async *chatStream(message, conversationHistory = [], contextData = null) {
		const response = await this.chat(
			message,
			conversationHistory,
			true,
			contextData,
		);

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

	const sendMessage = async (
		message,
		conversationHistory = [],
		contextData = null,
	) => {
		return execute(async () => {
			return assistantApi.chat(
				message,
				conversationHistory,
				false,
				contextData,
			);
		});
	};

	const sendStreamingMessage = async (
		message,
		conversationHistory = [],
		onChunk,
		contextData = null,
	) => {
		try {
			const stream = assistantApi.chatStream(
				message,
				conversationHistory,
				contextData,
			);
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
