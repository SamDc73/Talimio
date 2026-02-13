import { useDataStreamRuntime } from "@assistant-ui/react-data-stream"
import { useCallback, useMemo } from "react"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import { CSRF_HEADER_NAME, ensureCsrfToken } from "@/lib/csrf"
import logger from "@/lib/logger"
import { useContextualChat } from "./use-contextual-chat"

export const useAssistantRuntime = () => {
	const contextData = useContextualChat()
	const { claimPendingQuote, setInitialText } = useChatSidebar()

	const ctxType = contextData?.contextType || null
	const ctxId = contextData?.contextId ? String(contextData.contextId) : null
	const ctxMeta = contextData?.contextMeta || {}

	const toBlockquote = useCallback((rawText) => {
		return (rawText || "")
			.split("\n")
			.map((line) => (line.trim().length > 0 ? `> ${line}` : ">"))
			.join("\n")
			.trim()
	}, [])

	const headers = useCallback(async () => {
		// Always refresh before chat sends so data-stream requests do not fail on stale CSRF after server restarts.
		const csrfToken = await ensureCsrfToken({ forceRefresh: true })
		return csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}
	}, [])

	const body = useCallback(async () => {
		const payload = {
			context_type: ctxType,
			context_id: ctxId,
			context_meta: ctxMeta,
		}

		const rawQuote = claimPendingQuote() || ""
		const pendingQuote = toBlockquote(rawQuote)
		if (pendingQuote) {
			payload.pending_quote = pendingQuote
			setInitialText("")
			logger.info("included selection quote in first message", { quoteLength: pendingQuote.length })
		}

		return payload
	}, [claimPendingQuote, ctxId, ctxMeta, ctxType, setInitialText, toBlockquote])

	const runtimeOptions = useMemo(
		() => ({
			api: "/api/v1/assistant/chat",
			credentials: "include",
			headers,
			body,
			onResponse: () => {
				logger.track("assistant_chat_request")
			},
		}),
		[body, headers]
	)

	return useDataStreamRuntime(runtimeOptions)
}
