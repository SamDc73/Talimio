import { useApi } from "../hooks/useApi";
import { getUserHeaders } from "../utils/userUtils";

export const assistantApi = {
	async chat(message, conversationHistory = []) {
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
					user_id: getUserHeaders()["x-user-id"],
				}),
			},
		);

		if (!response.ok) {
			throw new Error("Failed to send message");
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

	return {
		sendMessage,
		loading,
		error,
	};
}
