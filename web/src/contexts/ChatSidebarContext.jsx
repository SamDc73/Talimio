import { createContext, useState } from "react"

// Chat sidebar context
export const ChatSidebarContext = createContext(undefined)

export function ChatSidebarProvider({ children }) {
	const [isChatOpen, setIsChatOpen] = useState(false)

	const toggleChat = () => {
		setIsChatOpen((prev) => !prev)
	}

	const closeChatSidebar = () => {
		setIsChatOpen(false)
	}

	return (
		<ChatSidebarContext.Provider value={{ isChatOpen, toggleChat, closeChatSidebar }}>
			{children}
		</ChatSidebarContext.Provider>
	)
}
