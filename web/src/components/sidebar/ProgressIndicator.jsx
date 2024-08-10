import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"

/**
 * Simple pill-style progress indicator component for sidebar
 * Shows completion percentage as a clean pill badge following styling guidelines
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 */
function ProgressIndicator({
	progress,
	suffix = "Completed",
	children,
	variant = "default",
	"data-testid": dataTestId,
}) {
	const isOpen = useAppStore(selectSidebarOpen)

	// Map variants to pill colors following the styling guide
	const variantStyles = {
		default: "bg-emerald-50 text-emerald-700",
		course: "bg-teal-50 text-teal-600", // Following styling guide
		book: "bg-blue-50 text-blue-600",
		video: "bg-violet-50 text-violet-600",
		flashcard: "bg-amber-50 text-amber-600",
	}

	const styleClass = variantStyles[variant] || variantStyles.default

	return (
		<div
			className={`flex items-center gap-2 px-4 pt-20 transition-opacity duration-300 ${
				isOpen ? "opacity-100" : "opacity-0"
			}`}
		>
			<span className={`${styleClass} text-xs font-semibold rounded-full px-3 py-1`} data-testid={dataTestId}>
				{progress}% {suffix}
			</span>
			{children}
		</div>
	)
}

export default ProgressIndicator
