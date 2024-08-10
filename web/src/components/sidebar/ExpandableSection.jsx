import { ChevronRight } from "lucide-react"

/**
 * Simple expandable section component with header and collapsible content
 * Used for modules, chapters, or any hierarchical navigation following original design
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 */
function ExpandableSection({
	title,
	isExpanded,
	onToggle,
	headerContent,
	children,
	className = "",
	isActive = false,
	showExpandButton = true,
	variant = "default",
}) {
	// Map variants to active border colors following the styling guide
	const variantColors = {
		default: "border-emerald-200 bg-emerald-50/50",
		course: "border-teal-200 bg-teal-50/50", // Following styling guide
		book: "border-blue-200 bg-blue-50/50",
		video: "border-violet-200 bg-violet-50/50",
		flashcard: "border-amber-200 bg-amber-50/50",
	}

	const activeStyle = variantColors[variant] || variantColors.default
	const chevronColor =
		variant === "course"
			? "text-teal-600"
			: variant === "book"
				? "text-blue-600"
				: variant === "video"
					? "text-violet-600"
					: variant === "flashcard"
						? "text-amber-600"
						: "text-emerald-600"

	return (
		<div
			className={`rounded-2xl border ${
				isActive ? activeStyle : "border-border bg-white"
			} shadow-sm overflow-hidden ${className}`}
		>
			<button
				type="button"
				className={`flex items-center gap-3 justify-between w-full px-4 py-3 text-left font-semibold text-sm text-foreground ${children && isExpanded ? "border-b border-border" : ""} rounded-t-2xl ${showExpandButton ? "cursor-pointer hover:bg-zinc-50/50" : ""} transition-colors`}
				style={{ background: isActive ? "transparent" : "#fff" }}
				onClick={showExpandButton ? onToggle : undefined}
				aria-expanded={showExpandButton ? isExpanded : undefined}
			>
				<div className="flex items-center gap-3 flex-1 min-w-0">
					{headerContent}
					<span className="line-clamp-2 text-sm">{title}</span>
				</div>
				{showExpandButton && (
					<ChevronRight
						className={`w-4 h-4 text-zinc-400 transition-transform duration-200 ${
							isExpanded ? `rotate-90 ${chevronColor}` : "rotate-0"
						}`}
					/>
				)}
			</button>
			{isExpanded && children && <div className="px-4 py-2 space-y-2">{children}</div>}
		</div>
	)
}

export default ExpandableSection
