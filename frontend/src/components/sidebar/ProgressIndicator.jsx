import { useSidebar } from "@/features/navigation/SidebarContext";

/**
 * Progress indicator component for sidebar
 * Shows completion percentage with customizable text
 */
function ProgressIndicator({ progress, suffix = "Completed", children }) {
	const { isOpen } = useSidebar();

	return (
		<div
			className={`flex items-center gap-2 px-4 pt-20 transition-opacity duration-300 ${
				isOpen ? "opacity-100" : "opacity-0"
			}`}
		>
			<span className="bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-full px-3 py-1">
				{progress}% {suffix}
			</span>
			{children}
		</div>
	);
}

export default ProgressIndicator;
