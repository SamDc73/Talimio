import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore";

/**
 * Progress indicator component for sidebar
 * Shows completion percentage with customizable text
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 */
function ProgressIndicator({
	progress,
	suffix = "Completed",
	children,
	variant = "default",
}) {
	const isOpen = useAppStore(selectSidebarOpen);

	// Map variants to styles
	const variantStyles = {
		default: "bg-emerald-100 text-emerald-700",
		course: "bg-course/10 text-course-text",
		book: "bg-book/10 text-book-text",
		video: "bg-video/10 text-video-text",
		flashcard: "bg-flashcard/10 text-flashcard-text",
		completed: "bg-completed/10 text-completed-text",
		upcoming: "bg-upcoming/10 text-upcoming-text",
		overdue: "bg-overdue/10 text-overdue-text",
		"due-today": "bg-due-today/10 text-due-today-text",
		paused: "bg-paused/10 text-paused-text",
	};

	const styleClass = variantStyles[variant] || variantStyles.default;

	return (
		<div
			className={`flex items-center gap-2 px-4 pt-20 transition-opacity duration-300 ${
				isOpen ? "opacity-100" : "opacity-0"
			}`}
		>
			<span
				className={`${styleClass} text-xs font-semibold rounded-full px-3 py-1`}
			>
				{progress}% {suffix}
			</span>
			{children}
		</div>
	);
}

export default ProgressIndicator;
