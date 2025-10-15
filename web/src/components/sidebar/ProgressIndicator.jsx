import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"

/**
 * Simple pill-style progress indicator component for sidebar
 * Shows completion percentage as a clean pill badge following styling guidelines
 * @param {string} variant - Content type variant: 'course', 'book', 'video'
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
		default: "bg-primary/10 text-primary",
		course: "bg-course/10 text-course",
		book: "bg-book/10 text-book",
		video: "bg-video/10 text-video",
	}

	const styleClass = variantStyles[variant] || variantStyles.default

	return (
		<div
			className={`flex items-center gap-2 px-5 py-6 transition-opacity duration-300 ${
				isOpen ? "opacity-100" : "opacity-0"
			}`}
		>
			<span
				className={`${styleClass} text-xs font-semibold rounded-full px-3 py-1.5 shadow-sm`}
				data-testid={dataTestId}
			>
				{progress}% {suffix}
			</span>
			{children}
		</div>
	)
}

export default ProgressIndicator
