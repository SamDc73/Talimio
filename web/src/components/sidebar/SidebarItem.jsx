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
			<div
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
				role="button"
				tabIndex={isLocked ? -1 : 0}
				onKeyDown={(e) => {
					if ((e.key === "Enter" || e.key === " ") && !isLocked) {
						e.preventDefault();
						onClick?.();
					}
				}}
				aria-label={`Navigate to ${title}`}
			>
				{title}
			</div>
			{rightContent}
		</li>
	);
}

export default SidebarItem;
