import { createContext, useContext } from "react"

// Context that carries chat sidebar state and actions
export const ChatSidebarContext = createContext(null)

// Hook for consuming the chat sidebar context
export function useChatSidebar() {
	const ctx = useContext(ChatSidebarContext)
	if (!ctx) {
		throw new Error("useChatSidebar must be used within a ChatSidebarProvider")
	}
	return ctx
}
