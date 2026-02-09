import { useLocalRuntime } from "@assistant-ui/react"
import { useCallback, useEffect, useMemo, useRef } from "react"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import { useAssistantModel } from "@/features/assistant/hooks/use-assistant-store"
import logger from "@/lib/logger"
import { assistantApi } from "../api/assistantApi"
import { useContextualChat } from "./use-contextual-chat"

export const useAssistantRuntime = () => {
	const assistantModel = useAssistantModel()
	const { contextData } = useContextualChat()
	const { initialText, setInitialText } = useChatSidebar()

	// Extract primitives to keep dependencies stable across renders
	const model = assistantModel || null
	const ctxType = contextData?.contextType || null
	const ctxId = contextData?.contextId ? String(contextData.contextId) : null
	const ctxMeta = contextData?.contextMeta || {}

	const makeQuote = useCallback(
		(s) =>
			(s || "")
				.split("\n")
				.map((line) => (line.trim().length > 0 ? `> ${line}` : ">"))
				.join("\n"),
		[]
	)

	// Keep latest quote and clear function in refs to avoid changing runtime identity
	const initialQuoteRef = useRef("")
	const clearInitialRef = useRef(() => {})

	const initialQuoteMemo = useMemo(() => (initialText ? makeQuote(initialText) : ""), [initialText, makeQuote])
	useEffect(() => {
		initialQuoteRef.current = initialQuoteMemo
	}, [initialQuoteMemo])
	useEffect(() => {
		clearInitialRef.current = setInitialText
	}, [setInitialText])

	// Helper: Extract plain text from assistant-ui message content parts
	const partsToText = useCallback((content) => {
		if (!content) return ""
		try {
			if (Array.isArray(content)) {
				return content
					.filter((p) => p && typeof p === "object" && p.type === "text" && typeof p.text === "string")
					.map((p) => p.text)
					.join("")
			}
			if (typeof content === "string") return content
			return ""
		} catch {
			return ""
		}
	}, [])

	// Stable run function to avoid recreating the runtime each render
	const run = useCallback(
		async function* run({ messages, abortSignal }) {
			const last = messages.at(-1)
			const lastMessageText0 = last ? partsToText(last.content) : ""
			if (!lastMessageText0.trim()) {
				return { content: [{ type: "text", text: "" }] }
			}

			// Include selection quote on first send if present
			const q = initialQuoteRef.current
			const lastMessageText = q ? `${q}\n\n${lastMessageText0}` : lastMessageText0
			if (q) {
				try {
					clearInitialRef.current("")
					logger.info("included selection quote in first message", { quoteLength: q.length })
				} catch {}
			}

			const conversationHistory = messages
				.slice(0, -1)
				.filter((m) => m.role === "user" || m.role === "assistant")
				.map((m) => ({ role: m.role, content: partsToText(m.content) }))

			const body = {
				message: lastMessageText,
				conversation_history: conversationHistory,
				stream: true,
				model: model,
				context_type: ctxType,
				context_id: ctxId,
				context_meta: ctxMeta,
			}

			logger.track("assistant_chat_request")

			const res = await assistantApi.createChatStream(body, abortSignal)

			const reader = res.body.getReader()
			const decoder = new TextDecoder("utf-8")
			let buffer = ""
			let accText = ""

			try {
				while (true) {
					const { value, done } = await reader.read()
					if (done) break
					buffer += decoder.decode(value, { stream: true })

					let idx = buffer.indexOf("\n\n")
					while (idx !== -1) {
						const eventChunk = buffer.slice(0, idx).trim()
						buffer = buffer.slice(idx + 2)

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

						if (dataStr === "[DONE]") {
							return { content: [{ type: "text", text: accText }] }
						}

						let payload
						try {
							payload = JSON.parse(dataStr)
						} catch {
							idx = buffer.indexOf("\n\n")
							continue
						}

						if (payload?.error) {
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
				} catch {}
			}

			return { content: [{ type: "text", text: accText }] }
		},
		// Only change when model/context primitives change
		[model, ctxType, ctxId, partsToText, ctxMeta]
	)

	// Memoize config object so useLocalRuntime sees stable input
	const runtime = useLocalRuntime(useMemo(() => ({ run }), [run]))

	return runtime
}
