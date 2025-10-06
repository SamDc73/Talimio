import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"

/**
 * Base container component for all sidebar implementations
 * Handles open/close animations and common styling
 */
function SidebarContainer({ children }) {
	const isOpen = useAppStore(selectSidebarOpen)

	return (
		<aside
			className={`fixed-sidebar flex flex-col bg-gradient-to-br from-white/98 to-slate-50/95 backdrop-blur-md rounded-br-2xl transition-all duration-300 ease-in-out ${
				isOpen ? "w-[320px] opacity-100 translate-x-0" : "w-0 opacity-0 -translate-x-full"
			}`}
			style={{
				boxShadow: isOpen ? "4px 0 24px rgba(0, 0, 0, 0.06), 0 4px 8px rgba(0, 0, 0, 0.04)" : "none",
			}}
		>
			{children}
		</aside>
	)
}

export default SidebarContainer
