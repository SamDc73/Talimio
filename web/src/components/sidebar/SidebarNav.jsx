import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"

/**
 * Navigation wrapper component for sidebar
 * Provides scrollable container with fade animations
 */
function SidebarNav({ children, className = "" }) {
	const isOpen = useAppStore(selectSidebarOpen)

	return (
		<nav
			className={`flex-1 px-4 pb-4 space-y-3 overflow-y-auto transition-opacity duration-300 ${
				isOpen ? "opacity-100" : "opacity-0"
			} ${className}`}
		>
			{children}
		</nav>
	)
}

export default SidebarNav
