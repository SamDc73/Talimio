import { useContext } from "react"

import { ChatSidebarContext } from "@/components/header/MainHeader"

export function useChatSidebar() {
	const context = useContext(ChatSidebarContext)
	// Return a default context if used outside provider to prevent errors
	if (context === undefined) {
		return {
			isChatOpen: false,
			toggleChat: () => {},
			closeChatSidebar: () => {},
		}
	}
	return context
}
