import { CheckCircle, Circle, MinusSquare } from "lucide-react"

/**
 * Simple completion checkbox component for sidebar items
 * Shows either a checkmark or empty circle with contextual colors following styling guide
 * @param {string} variant - Content type variant: 'course', 'book', 'video'
 * @param {boolean} asDiv - Render as span instead of button to avoid nested button warnings
 */
function CompletionCheckbox({
	isCompleted,
	isIndeterminate = false,
	isLocked = false,
	onClick,
	variant = "default",
	asDiv = false,
	"data-testid": dataTestId,
}) {
	// Map variants to colors following the styling guide
	const variantColors = {
		default: "text-primary",
		course: "text-course",
		book: "text-book",
		video: "text-video",
	}

	const completedColor = variantColors[variant] || variantColors.default

	const renderIcon = () => {
		if (isIndeterminate) {
			return <MinusSquare className={`size-5  ${completedColor}`} />
		}
		if (isCompleted) {
			return <CheckCircle className={`size-5  ${completedColor}`} />
		}
		return <Circle className={`size-5 ${isLocked ? "text-border" : "text-muted-foreground/35 hover:text-muted-foreground/70"}`} />
	}

	const handleClick = (e) => {
		e.stopPropagation()
		if (!isLocked && onClick) {
			onClick(e)
		}
	}

	const baseClasses = "-m-1 mt-0.5 rounded-full p-1 transition-all duration-200 hover:scale-110 hover:bg-muted/60"

	if (asDiv) {
		return (
			<button
				type="button"
				onClick={handleClick}
				className={`inline-block ${baseClasses} cursor-pointer ${isLocked ? "opacity-50 cursor-not-allowed" : ""}`}
				data-testid={dataTestId}
				disabled={isLocked}
				aria-label={isCompleted ? "Mark as incomplete" : "Mark as complete"}
			>
				{renderIcon()}
			</button>
		)
	}

	return (
		<button
			type="button"
			onClick={handleClick}
			className={baseClasses}
			disabled={isLocked}
			data-testid={dataTestId}
			aria-label={isCompleted ? "Mark as incomplete" : "Mark as complete"}
		>
			{renderIcon()}
		</button>
	)
}

export default CompletionCheckbox
