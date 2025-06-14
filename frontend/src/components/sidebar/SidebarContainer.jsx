import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore";

/**
 * Base container component for all sidebar implementations
 * Handles open/close animations and common styling
 */
function SidebarContainer({ children }) {
	const isOpen = useAppStore(selectSidebarOpen);

	return (
		<aside
			className={`fixed-sidebar flex flex-col bg-white border-r border-border transition-all duration-300 ease-in-out ${
				isOpen
					? "w-[320px] opacity-100 translate-x-0"
					: "w-0 opacity-0 -translate-x-full"
			}`}
			style={{ boxShadow: isOpen ? "0 4px 20px rgba(0, 0, 0, 0.05)" : "none" }}
		>
			{children}
		</aside>
	);
}

export default SidebarContainer;
