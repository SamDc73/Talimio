import { useCallback, useEffect, useState } from "react"
import { ChatSidebarContext } from "@/contexts/ChatSidebarContext"
import { ChatSidebar } from "@/features/assistant/components/ChatSidebar"
import { useAssistantPinned } from "@/features/assistant/hooks/use-assistant-store"

export function ChatSidebarProvider({ children }) {
	const [isOpen, setIsOpen] = useState(false)
	const [initialText, setInitialText] = useState("")
	const [pendingQuote, setPendingQuote] = useState("")
	const assistantSidebarPinned = useAssistantPinned()

	const openChat = useCallback((text = "") => {
		setInitialText(text)
		setIsOpen(true)
	}, [])
	const closeChat = useCallback(() => setIsOpen(false), [])
	const toggleChat = useCallback(() => setIsOpen((v) => !v), [])

	const claimPendingQuote = useCallback(() => {
		const q = pendingQuote || initialText || ""
		if (pendingQuote) setPendingQuote("")
		return q
	}, [pendingQuote, initialText])

	// Listen for open assistant events - needs to live here so it works
	// even when the sidebar itself isn't mounted
	useEffect(() => {
		const handleOpenAssistant = () => toggleChat()
		window.addEventListener("openAssistant", handleOpenAssistant)
		return () => window.removeEventListener("openAssistant", handleOpenAssistant)
	}, [toggleChat])

	const value = {
		isOpen,
		openChat,
		closeChat,
		toggleChat,
		initialText,
		setInitialText,
		setPendingQuote,
		claimPendingQuote,
	}

	return (
		<ChatSidebarContext.Provider value={value}>
			{children}
			{(isOpen || assistantSidebarPinned) && <ChatSidebar isOpen={isOpen} onToggle={toggleChat} onClose={closeChat} />}
		</ChatSidebarContext.Provider>
	)
}
