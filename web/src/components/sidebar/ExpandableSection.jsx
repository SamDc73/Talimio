import { ChevronRight } from "lucide-react"

/**
 * Simple expandable section component with header and collapsible content
 * Used for modules, chapters, or any hierarchical navigation following original design
 * @param {string} variant - Content type variant: 'course', 'book', 'video'
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
		default: "border-border bg-card",
		course: "border-course/40 bg-course/5",
		book: "border-book/40 bg-book/5",
		video: "border-video/40 bg-video/5",
	}

	const activeStyle = variantColors[variant] || variantColors.default
	let chevronColor = "text-primary"
	switch (variant) {
		case "course": {
			chevronColor = "text-course"

			break
		}
		case "book": {
			chevronColor = "text-book"

			break
		}
		case "video": {
			chevronColor = "text-video"

			break
		}
		// No default
	}

	return (
		<div
			className={`rounded-xl border ${
				isActive ? activeStyle : "border-border bg-card"
			} shadow-sm transition-shadow duration-200 hover:shadow-md overflow-hidden ${className}`}
		>
			<button
				type="button"
				className={`flex items-center gap-3 justify-between w-full px-4 py-3 text-left font-semibold text-sm text-foreground ${children && isExpanded ? "border-b border-border/60" : ""} rounded-t-xl ${showExpandButton ? "cursor-pointer hover:bg-muted/60" : ""} transition-colors`}
				style={{ background: isActive ? "transparent" : "var(--color-card)" }}
				onClick={showExpandButton ? onToggle : undefined}
				aria-expanded={showExpandButton ? isExpanded : undefined}
			>
				<div className="flex items-center gap-3 flex-1 min-w-0">
					{headerContent}
					<span className="line-clamp-2 text-sm">{title}</span>
				</div>
				{showExpandButton && (
					<ChevronRight
						className={`size-4  text-muted-foreground/80 transition-transform duration-200 ${
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
