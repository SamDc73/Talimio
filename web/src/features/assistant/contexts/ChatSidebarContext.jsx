import { useState } from "react"
import { ChatSidebarContext } from "@/contexts/chatSidebarContext"
import { ChatSidebar } from "@/features/assistant/components/ChatSidebar"

export function ChatSidebarProvider({ children }) {
	const [isOpen, setIsOpen] = useState(false)
	const [initialText, setInitialText] = useState("")
	// Store a one-time quote to attach to the very next user message
	const [pendingQuote, setPendingQuote] = useState("")

	const openChat = (text = "") => {
		setInitialText(text)
		setIsOpen(true)
	}
	const closeChat = () => setIsOpen(false)
	const toggleChat = () => setIsOpen((v) => !v)

	// Expose initialText to allow runtime/UI to read/clear selection context
	const claimPendingQuote = () => {
		const q = pendingQuote || initialText || ""
		if (pendingQuote) setPendingQuote("")
		return q
	}

	const value = {
		isOpen,
		openChat,
		closeChat,
		toggleChat,
		initialText,
		setInitialText,
		// quote handoff for next sent message
		setPendingQuote,
		claimPendingQuote,
	}

	return (
		<ChatSidebarContext.Provider value={value}>
			{children}
			{/* Render the sidebar once at app-root level */}
			<ChatSidebar isOpen={isOpen} onToggle={toggleChat} onClose={closeChat} />
		</ChatSidebarContext.Provider>
	)
}
