import { createContext, useContext } from "react"

export const ChatSidebarContext = createContext(null)

export function useChatSidebar() {
	const ctx = useContext(ChatSidebarContext)
	if (!ctx) {
		throw new Error("useChatSidebar must be used within a ChatSidebarProvider")
	}
	return ctx
}
