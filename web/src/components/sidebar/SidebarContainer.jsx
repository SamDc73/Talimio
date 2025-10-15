import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"

/**
 * Base container component for all sidebar implementations
 * Handles open/close animations and common styling
 */
function SidebarContainer({ children }) {
	const isOpen = useAppStore(selectSidebarOpen)

	return (
		<aside
			className={cn(
				"fixed left-0 top-0 z-20 flex h-screen flex-col overflow-y-auto rounded-br-2xl bg-gradient-to-br from-background/95 to-muted/90 backdrop-blur-md transition-all duration-300 ease-in-out",
				isOpen ? "w-80 translate-x-0 opacity-100" : "w-0 -translate-x-full opacity-0"
			)}
			style={{
				boxShadow: isOpen ? "4px 0 24px rgba(0, 0, 0, 0.06), 0 4px 8px rgba(0, 0, 0, 0.04)" : "none",
			}}
		>
			{children}
		</aside>
	)
}

export default SidebarContainer
