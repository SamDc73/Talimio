/**
 * Simple generic sidebar item component
 * Handles click events and active states following original design
 * @param {string} variant - Content type variant: 'course', 'book', 'video'
 */
function SidebarItem({
	title,
	isActive = false,
	isCompleted = false,
	isLocked = false,
	onClick,
	leftContent,
	rightContent,
	className = "",
	variant = "default",
}) {
	// Validate that leftContent and rightContent are not buttons if onClick is provided
	if (process.env.NODE_ENV === "development") {
		if (onClick && leftContent?.type === "button") {
		}
		if (onClick && rightContent?.type === "button") {
		}
	}
	// Map variants to colors following the styling guide
	const variantColors = {
		default: "text-primary",
		course: "text-course",
		book: "text-book",
		video: "text-video",
	}

	const activeColor = variantColors[variant] || variantColors.default

	return (
		<li className={`flex items-start gap-3 ${className}`}>
			{leftContent}
			<button
				type="button"
				disabled={isLocked}
				className={`text-left flex-1 min-w-0 ${
					isCompleted ? `font-semibold ${activeColor}` : isActive ? `font-semibold ${activeColor}` : "text-zinc-800"
				}`}
				style={{
					background: "none",
					border: "none",
					padding: 0,
					cursor: isLocked ? "not-allowed" : "pointer",
				}}
				onClick={() => !isLocked && onClick?.()}
				aria-label={`Navigate to ${title}`}
			>
				{title}
			</button>
			{rightContent}
		</li>
	)
}

export default SidebarItem
