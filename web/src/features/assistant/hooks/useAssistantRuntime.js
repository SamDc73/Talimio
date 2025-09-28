import { useLocalRuntime } from "@assistant-ui/react"
import { useAssistantModel } from "@/features/assistant/hooks/assistant-store"
import logger from "@/lib/logger"
import { assistantApi } from "../api/assistantApi"
import { useContextualChat } from "./useContextualChat"

export const useAssistantRuntime = () => {
	const assistantModel = useAssistantModel()
	const { contextData } = useContextualChat()

	// Local runtime gives us full control over the request shape (API-first)
	const runtime = useLocalRuntime({
		async *run({ messages, abortSignal }) {
			// Helper: Extract plain text from assistant-ui message content parts
			const partsToText = (content) => {
				if (!content) return ""
				try {
					// content may be an array of parts: [{ type: 'text', text: '...' }, ...]
					if (Array.isArray(content)) {
						return content
							.filter((p) => p && typeof p === "object" && p.type === "text" && typeof p.text === "string")
							.map((p) => p.text)
							.join("")
					}
					// or already a string (defensive)
					if (typeof content === "string") return content
					return ""
				} catch {
					// Silent fail - content parsing errors are non-critical
					return ""
				}
			}

			// Build ChatRequest payload expected by backend
			const last = messages[messages.length - 1]
			const lastMessageText = last ? partsToText(last.content) : ""
			if (!lastMessageText.trim()) {
				// Nothing to send, stop early
				return { content: [{ type: "text", text: "" }] }
			}

			const conversationHistory = messages
				.slice(0, -1)
				.filter((m) => m.role === "user" || m.role === "assistant")
				.map((m) => ({ role: m.role, content: partsToText(m.content) }))

			const body = {
				message: lastMessageText,
				conversation_history: conversationHistory,
				stream: true,
				model: assistantModel || null,
				context_type: contextData.contextType || null,
				context_id: contextData.contextId ? String(contextData.contextId) : null,
				context_meta: contextData.contextMeta || {},
			}

			// Track chat usage for analytics
			logger.track("assistant_chat_request")

			const res = await assistantApi.createChatStream(body, abortSignal)

			// Parse SSE stream from backend
			const reader = res.body.getReader()
			const decoder = new TextDecoder("utf-8")
			let buffer = ""
			let accText = ""

			try {
				while (true) {
					const { value, done } = await reader.read()
					if (done) break
					buffer += decoder.decode(value, { stream: true })

					// Split by event delimiter (blank line) per SSE spec
					let idx = buffer.indexOf("\n\n")
					while (idx !== -1) {
						const eventChunk = buffer.slice(0, idx).trim()
						buffer = buffer.slice(idx + 2)

						// Extract data: lines
						const dataLines = eventChunk
							.split("\n")
							.map((l) => l.trim())
							.filter((l) => l.startsWith("data:"))
						if (dataLines.length === 0) {
							idx = buffer.indexOf("\n\n")
							continue
						}
						const dataStr = dataLines.map((l) => l.slice(5).trim()).join("\n")
						if (!dataStr) {
							idx = buffer.indexOf("\n\n")
							continue
						}

						// Handle special terminator
						if (dataStr === "[DONE]") {
							return { content: [{ type: "text", text: accText }] }
						}

						// Parse backend JSON: { content: string, done: bool } or { error: string, done: true }
						let payload
						try {
							payload = JSON.parse(dataStr)
						} catch {
							// Skip malformed JSON - likely a partial message
							idx = buffer.indexOf("\n\n")
							continue
						}

						if (payload?.error) {
							// Emit final error as text and stop
							accText = accText || ""
							accText += `${accText ? "\n\n" : ""}Error: ${payload.error}`
							yield { content: [{ type: "text", text: accText }] }
							return { content: [{ type: "text", text: accText }] }
						}

						const delta = typeof payload?.content === "string" ? payload.content : ""
						if (delta) {
							accText += delta
							yield { content: [{ type: "text", text: accText }] }
						}

						if (payload?.done) {
							return { content: [{ type: "text", text: accText }] }
						}

						idx = buffer.indexOf("\n\n")
					}
				}
			} finally {
				try {
					reader.releaseLock()
				} catch {
					// Silent fail - reader might already be released
				}
			}

			return { content: [{ type: "text", text: accText }] }
		},
	})

	return runtime
}
