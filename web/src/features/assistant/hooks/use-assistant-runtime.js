import {
	CompositeAttachmentAdapter,
	RuntimeAdapterProvider,
	SimpleImageAttachmentAdapter,
	useAui,
	useAuiState,
	unstable_useRemoteThreadListRuntime as useRemoteThreadListRuntime,
} from "@assistant-ui/react"
import { useDataStreamRuntime } from "@assistant-ui/react-data-stream"
import { createElement, useCallback, useEffect, useMemo, useRef } from "react"
import { useChatSidebar } from "@/contexts/ChatSidebarContext"
import { assistantApi } from "@/features/assistant/api/assistantApi"
import { getAssistantToolRenderers } from "@/features/assistant/assistantToolRenderers"
import { getApiUrl } from "@/lib/apiBase"
import { getCsrfHeaders } from "@/lib/csrf"
import logger from "@/lib/logger"
import { useContextualChat } from "./use-contextual-chat"

const MAX_GENERATED_TITLE_LENGTH = 80
const UNSTABLE_PROVIDER_KEY = "unstable_Provider"
const UNAUTHORIZED_STATUS_CODES = new Set([401, 403])

const isUnauthorizedError = (error) => {
	const status = error?.status
	return typeof status === "number" && UNAUTHORIZED_STATUS_CODES.has(status)
}

const toContextModelConfig = (conversationContext) => {
	if (!conversationContext?.contextType || !conversationContext?.contextId) {
		return null
	}

	return {
		context_type: conversationContext.contextType,
		context_id: conversationContext.contextId,
		context_meta: conversationContext.contextMeta || {},
	}
}

const mapConversationToThreadMetadata = (conversation) => {
	return {
		remoteId: String(conversation.remoteId),
		externalId: conversation.externalId || undefined,
		status: "regular",
		title: conversation.title || conversation.lastMessagePreview || undefined,
	}
}

const ensureThreadMessageMetadata = (message) => {
	if (!message || typeof message !== "object") {
		return message
	}

	const metadata = message.metadata
	const shouldNormalizeMetadata = !metadata || typeof metadata !== "object" || Array.isArray(metadata)
	const isUserMessage = message.role === "user"
	const rawAttachments = isUserMessage && Array.isArray(message.attachments) ? message.attachments : null
	const normalizedAttachments = isUserMessage
		? (rawAttachments || []).filter(
				(attachment) => attachment && typeof attachment === "object" && attachment.type === "image"
			)
		: undefined
	const shouldNormalizeAttachments =
		isUserMessage &&
		(!Array.isArray(message.attachments) || (rawAttachments && normalizedAttachments.length !== rawAttachments.length))

	if (!shouldNormalizeMetadata && !shouldNormalizeAttachments) {
		return message
	}

	return {
		...message,
		...(shouldNormalizeAttachments ? { attachments: normalizedAttachments } : {}),
		metadata: shouldNormalizeMetadata ? {} : metadata,
	}
}

const normalizeHistoryRepository = (repositoryPayload) => {
	const messages = Array.isArray(repositoryPayload?.messages) ? repositoryPayload.messages : []

	return {
		...repositoryPayload,
		messages: messages.map((item) => {
			if (!item || typeof item !== "object") {
				return item
			}

			return {
				...item,
				message: ensureThreadMessageMetadata(item.message),
			}
		}),
	}
}

const extractTextFromMessage = (message) => {
	if (!message || typeof message !== "object") {
		return ""
	}

	let content = []
	if (Array.isArray(message.content)) {
		content = message.content
	} else if (Array.isArray(message.parts)) {
		content = message.parts
	}
	if (content.length === 0) {
		return ""
	}

	const textParts = []
	for (const part of content) {
		if (!part || typeof part !== "object") {
			continue
		}
		if (part.type !== "text") {
			continue
		}
		if (typeof part.text !== "string") {
			continue
		}
		const normalizedText = part.text.trim()
		if (normalizedText) {
			textParts.push(normalizedText)
		}
	}

	return textParts.join(" ").replace(/\s+/g, " ").trim()
}

const buildGeneratedTitle = (messages) => {
	if (!Array.isArray(messages) || messages.length === 0) {
		return ""
	}

	for (const message of messages) {
		if (!message || typeof message !== "object") {
			continue
		}
		if (message.role !== "user") {
			continue
		}
		const text = extractTextFromMessage(message)
		if (!text) {
			continue
		}
		return text.slice(0, MAX_GENERATED_TITLE_LENGTH)
	}

	return ""
}

const createTitleStream = (title) => {
	return new ReadableStream({
		start(controller) {
			if (title) {
				controller.enqueue({
					type: "part-start",
					path: [],
					part: { type: "text" },
				})
				controller.enqueue({
					type: "text-delta",
					path: [0],
					textDelta: title,
				})
				controller.enqueue({
					type: "part-finish",
					path: [0],
				})
				controller.enqueue({
					type: "message-finish",
					path: [],
					finishReason: "stop",
					usage: { promptTokens: 0, completionTokens: 0 },
				})
			}
			controller.close()
		},
	})
}

const useAssistantDataStreamRuntime = () => {
	const aui = useAui()
	const { claimPendingQuote, setInitialText } = useChatSidebar()

	const toBlockquote = useCallback((rawText) => {
		return (rawText || "")
			.split("\n")
			.map((line) => (line.trim().length > 0 ? `> ${line}` : ">"))
			.join("\n")
			.trim()
	}, [])

	const headers = useCallback(async () => {
		// Keep the existing CSRF token stable during send so concurrent history writes and chat POST share the same token.
		return getCsrfHeaders()
	}, [])

	const body = useCallback(async () => {
		const { remoteId } = await aui.threadListItem().initialize()
		const payload = {
			threadId: remoteId,
		}

		const rawQuote = claimPendingQuote() || ""
		const pendingQuote = toBlockquote(rawQuote)
		if (pendingQuote) {
			payload.pending_quote = pendingQuote
			setInitialText("")
		}

		return payload
	}, [aui, claimPendingQuote, setInitialText, toBlockquote])

	return useDataStreamRuntime(
		useMemo(
			() => ({
				api: getApiUrl("/assistant/chat"),
				credentials: "include",
				headers,
				body,
				sendExtraMessageFields: true,
			}),
			[body, headers]
		)
	)
}

function ThreadRuntimeAdaptersProvider({ children, getConversationContext, fallbackContext }) {
	const aui = useAui()
	const remoteId = useAuiState((state) => state.threadListItem.remoteId)

	const attachments = useMemo(() => new CompositeAttachmentAdapter([new SimpleImageAttachmentAdapter()]), [])

	const conversationContext = useMemo(() => {
		if (remoteId) {
			const storedContext = getConversationContext(remoteId)
			if (storedContext) {
				return storedContext
			}
			return null
		}
		return fallbackContext
	}, [fallbackContext, getConversationContext, remoteId])

	const contextConfig = useMemo(() => toContextModelConfig(conversationContext), [conversationContext])

	useEffect(() => {
		if (!contextConfig) {
			return
		}

		return aui.modelContext().register({
			getModelContext: () => ({
				config: contextConfig,
			}),
		})
	}, [aui, contextConfig])

	const history = useMemo(
		() => ({
			async load() {
				const threadState = aui.threadListItem().getState()
				if (!threadState.remoteId) {
					return { messages: [] }
				}
				const repositoryPayload = await assistantApi.getConversationHistory(threadState.remoteId)
				return normalizeHistoryRepository(repositoryPayload)
			},

			async append(item) {
				const threadState = await aui.threadListItem().initialize()
				const normalizedItem = {
					...item,
					message: ensureThreadMessageMetadata(item?.message),
				}
				await assistantApi.appendConversationHistory(threadState.remoteId, normalizedItem)
			},
		}),
		[aui]
	)

	const adapters = useMemo(() => ({ history, attachments }), [attachments, history])
	return createElement(RuntimeAdapterProvider, { adapters }, children)
}

export const useAssistantRuntime = () => {
	const contextData = useContextualChat()
	const contextType = contextData?.contextType || null
	const contextId = contextData?.contextId ? String(contextData.contextId) : null
	const contextMetaKey = JSON.stringify(contextData?.contextMeta || {})
	const normalizedContextMeta = useMemo(() => JSON.parse(contextMetaKey), [contextMetaKey])
	const conversationSeed = useMemo(() => {
		if (!contextType || !contextId) {
			return null
		}

		return {
			contextType,
			contextId,
			contextMeta: normalizedContextMeta,
		}
	}, [contextId, contextType, normalizedContextMeta])
	const conversationContextByRemoteIdRef = useRef(new Map())

	const storeConversationContext = useCallback((conversation) => {
		const remoteId = conversation?.remoteId
		if (!remoteId) {
			return
		}

		const contextType = conversation?.contextType || null
		const contextId = conversation?.contextId ? String(conversation.contextId) : null
		if (!contextType || !contextId) {
			conversationContextByRemoteIdRef.current.delete(String(remoteId))
			return
		}

		conversationContextByRemoteIdRef.current.set(String(remoteId), {
			contextType,
			contextId,
			contextMeta: conversation?.contextMeta || {},
		})
	}, [])

	const getConversationContext = useCallback((remoteId) => {
		return conversationContextByRemoteIdRef.current.get(String(remoteId)) || null
	}, [])

	const threadListAdapter = useMemo(
		() => ({
			async list() {
				try {
					const payload = await assistantApi.listConversations({ limit: 100 })
					const items = Array.isArray(payload?.items) ? payload.items : []

					const dedupedItems = []
					const seenRemoteIds = new Set()
					for (const item of items) {
						const remoteId = item?.remoteId ? String(item.remoteId) : null
						if (!remoteId || seenRemoteIds.has(remoteId)) {
							continue
						}
						seenRemoteIds.add(remoteId)
						dedupedItems.push(item)
						storeConversationContext(item)
					}

					return {
						threads: dedupedItems.map((conversation) => mapConversationToThreadMetadata(conversation)),
					}
				} catch (error) {
					if (isUnauthorizedError(error)) {
						logger.warn("assistant conversation list unauthorized; returning empty thread list")
						return { threads: [] }
					}
					throw error
				}
			},

			async initialize(_localId) {
				const payload = conversationSeed
					? {
							contextType: conversationSeed.contextType,
							contextId: conversationSeed.contextId,
							contextMeta: conversationSeed.contextMeta,
						}
					: {}
				const response = await assistantApi.createConversation(payload)
				const remoteId = String(response.remoteId)

				if (conversationSeed) {
					conversationContextByRemoteIdRef.current.set(remoteId, conversationSeed)
				}

				return { remoteId, externalId: undefined }
			},

			async fetch(remoteId) {
				const conversation = await assistantApi.getConversation(remoteId)
				storeConversationContext(conversation)
				return mapConversationToThreadMetadata(conversation)
			},

			async rename(remoteId, title) {
				const conversation = await assistantApi.renameConversation(remoteId, title)
				storeConversationContext(conversation)
			},

			async archive(_remoteId) {},

			async unarchive(_remoteId) {},

			async delete(remoteId) {
				await assistantApi.deleteConversation(remoteId)
				conversationContextByRemoteIdRef.current.delete(String(remoteId))
			},

			async generateTitle(remoteId, messages) {
				const generatedTitle = buildGeneratedTitle(messages)
				if (!generatedTitle) {
					return createTitleStream("")
				}

				const conversation = await assistantApi.renameConversation(remoteId, generatedTitle)
				storeConversationContext(conversation)
				return createTitleStream(generatedTitle)
			},

			[UNSTABLE_PROVIDER_KEY]: ({ children }) => {
				return createElement(
					ThreadRuntimeAdaptersProvider,
					{
						getConversationContext,
						fallbackContext: conversationSeed,
					},
					children
				)
			},
		}),
		[conversationSeed, getConversationContext, storeConversationContext]
	)

	const runtime = useRemoteThreadListRuntime({
		runtimeHook: useAssistantDataStreamRuntime,
		adapter: threadListAdapter,
	})

	const toolRenderers = useMemo(() => getAssistantToolRenderers(), [])
	return { runtime, toolRenderers }
}
