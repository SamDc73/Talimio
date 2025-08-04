import CompletionCheckbox from "../sidebar/CompletionCheckbox";

/**
 * InteractiveListItem - Reusable pattern for list items with interactive elements
 *
 * This component enforces the pattern of non-nested interactive elements by ensuring
 * checkbox and button are siblings, not parent-child.
 *
 * @param {Object} props
 * @param {Object} props.checkbox - Checkbox configuration { isCompleted: boolean }
 * @param {Function} props.onToggle - Handler for checkbox toggle
 * @param {Function} props.onClick - Handler for main content click
 * @param {React.ReactNode} props.children - Content to display in the button
 * @param {boolean} props.isActive - Whether the item is currently active
 * @param {string} props.variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 * @param {string} props.className - Additional CSS classes
 */
export function InteractiveListItem({
	checkbox,
	onToggle,
	onClick,
	children,
	isActive = false,
	variant = "default",
	className = "",
}) {
	const baseClasses = `flex items-center gap-3 ${isActive ? "bg-blue-50" : ""} ${className}`;

	return (
		<div className={baseClasses}>
			{checkbox && (
				<CompletionCheckbox
					asDiv={true} // Always true in this context to avoid nesting
					isCompleted={checkbox.isCompleted}
					onClick={(e) => {
						e.stopPropagation();
						onToggle?.();
					}}
					variant={variant}
				/>
			)}
			<button
				type="button"
				onClick={onClick}
				className="flex-1 text-left hover:underline"
			>
				{children}
			</button>
		</div>
	);
}

export default InteractiveListItem;
