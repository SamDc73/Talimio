import { useState } from "react"
import { ChatSidebar } from "../components/ChatSidebar"
import { ChatSidebarContext } from "./chatSidebarContext"

export function ChatSidebarProvider({ children }) {
	const [isOpen, setIsOpen] = useState(false)
	const [initialText, setInitialText] = useState("")

	const openChat = (text = "") => {
		setInitialText(text)
		setIsOpen(true)
	}
	const closeChat = () => setIsOpen(false)
	const toggleChat = () => setIsOpen((v) => !v)

	// Expose initialText to allow runtime/UI to read/clear selection context
	const value = { isOpen, openChat, closeChat, toggleChat, initialText, setInitialText }

	return (
		<ChatSidebarContext.Provider value={value}>
			{children}
			{/* Render the sidebar once at app-root level */}
			<ChatSidebar isOpen={isOpen} onToggle={toggleChat} onClose={closeChat} />
		</ChatSidebarContext.Provider>
	)
}
