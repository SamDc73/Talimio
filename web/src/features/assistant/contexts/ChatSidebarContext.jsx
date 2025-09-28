import { useState } from "react"
import { ChatSidebar } from "../components/ChatSidebar"
import { ChatSidebarContext } from "./chatSidebarContext"

export function ChatSidebarProvider({ children }) {
	const [isOpen, setIsOpen] = useState(false)

	const openChat = () => setIsOpen(true)
	const closeChat = () => setIsOpen(false)
	const toggleChat = () => setIsOpen((v) => !v)

	const value = { isOpen, openChat, closeChat, toggleChat }

	return (
		<ChatSidebarContext.Provider value={value}>
			{children}
			{/* Render the sidebar once at app-root level */}
			<ChatSidebar isOpen={isOpen} onToggle={toggleChat} onClose={closeChat} />
		</ChatSidebarContext.Provider>
	)
}
