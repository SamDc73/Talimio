/**
 * Simple generic sidebar item component
 * Handles click events and active states following original design
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
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
			console.warn(
				"SidebarItem: leftContent should not be a button when onClick is provided. Use asDiv prop.",
			);
		}
		if (onClick && rightContent?.type === "button") {
			console.warn(
				"SidebarItem: rightContent should not be a button when onClick is provided. Use asDiv prop.",
			);
		}
	}
	// Map variants to colors following the styling guide
	const variantColors = {
		default: "text-emerald-700",
		course: "text-teal-600", // Following styling guide
		book: "text-blue-600",
		video: "text-violet-600",
		flashcard: "text-amber-600",
	};

	const activeColor = variantColors[variant] || variantColors.default;

	return (
		<li className={`flex items-start gap-3 ${className}`}>
			{leftContent}
			<button
				type="button"
				disabled={isLocked}
				className={`text-left flex-1 min-w-0 ${
					isCompleted
						? `font-semibold ${activeColor}`
						: isActive
							? `font-semibold ${activeColor}`
							: "text-zinc-800"
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
	);
}

export default SidebarItem;
