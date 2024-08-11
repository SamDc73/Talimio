import { X } from "lucide-react"

/**
 * Reusable Tag component for displaying tags with different variants and interactions
 */
const Tag = ({
	tag,
	variant = "default", // "default", "removable", "clickable", "selected"
	size = "medium", // "small", "medium", "large"
	onRemove,
	onClick,
	className = "",
	...props
}) => {
	// Base styles
	const baseStyles = "inline-flex items-center gap-1 font-medium rounded-full border transition-all duration-200"

	// Size variants
	const sizeStyles = {
		small: "px-2 py-0.5 text-xs",
		medium: "px-3 py-1 text-sm",
		large: "px-4 py-1.5 text-base",
	}

	// Variant styles
	const variantStyles = {
		default: "bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200",
		removable: "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100",
		clickable: "bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200 cursor-pointer",
		selected: "bg-blue-100 text-blue-800 border-blue-300 ring-2 ring-blue-200",
	}

	// Get tag color if available
	const tagColor = tag?.color
	const customColorStyles = tagColor
		? {
				backgroundColor: `${tagColor}20`,
				color: tagColor,
				borderColor: `${tagColor}40`,
			}
		: {}

	// Handle click
	const handleClick = (e) => {
		if (onClick) {
			e.preventDefault()
			e.stopPropagation()
			onClick(tag)
		}
	}

	// Handle remove
	const handleRemove = (e) => {
		e.preventDefault()
		e.stopPropagation()
		if (onRemove) {
			onRemove(tag)
		}
	}

	const Component = onClick ? "button" : "span"

	return (
		<Component
			type={onClick ? "button" : undefined}
			className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
			style={customColorStyles}
			onClick={handleClick}
			{...props}
		>
			{/* Tag name */}
			<span className="truncate max-w-32">{typeof tag === "string" ? tag : tag?.name || "Unknown"}</span>

			{/* Remove button for removable variant */}
			{variant === "removable" && onRemove && (
				<button
					type="button"
					onClick={handleRemove}
					className="ml-1 hover:bg-red-100 hover:text-red-600 rounded-full p-0.5 transition-colors"
					aria-label="Remove tag"
				>
					<X size={size === "small" ? 10 : size === "large" ? 16 : 12} />
				</button>
			)}
		</Component>
	)
}

/**
 * TagList component for displaying multiple tags
 */
export const TagList = ({
	tags = [],
	variant = "default",
	size = "medium",
	onTagClick,
	onTagRemove,
	maxVisible = null,
	className = "",
	...props
}) => {
	const visibleTags = maxVisible ? tags.slice(0, maxVisible) : tags
	const hiddenCount = maxVisible ? Math.max(0, tags.length - maxVisible) : 0

	if (!tags || tags.length === 0) {
		return null
	}

	return (
		<div className={`flex flex-wrap gap-1 ${className}`} {...props}>
			{visibleTags.map((tag, index) => (
				<Tag
					key={tag?.id || tag?.name || index}
					tag={tag}
					variant={variant}
					size={size}
					onClick={onTagClick}
					onRemove={onTagRemove}
				/>
			))}
			{hiddenCount > 0 && <span className="text-xs text-gray-500 px-2 py-1">+{hiddenCount} more</span>}
		</div>
	)
}

export default Tag
