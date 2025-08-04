import { useContext } from "react";
import { ChatSidebarContext } from "@/components/header/MainHeader";

export function useChatSidebar() {
	const context = useContext(ChatSidebarContext);
	// Return a default context if used outside provider to prevent errors
	if (context === undefined) {
		return {
			isChatOpen: false,
			toggleChat: () => {
				console.warn(
					"ChatSidebar: toggleChat called outside of ChatSidebarProvider",
				);
			},
			closeChatSidebar: () => {
				console.warn(
					"ChatSidebar: closeChatSidebar called outside of ChatSidebarProvider",
				);
			},
		};
	}
	return context;
}
