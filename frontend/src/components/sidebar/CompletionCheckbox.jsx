import { CheckCircle, Circle, MinusSquare } from "lucide-react";

/**
 * Simple completion checkbox component for sidebar items
 * Shows either a checkmark or empty circle with contextual colors following styling guide
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 */
function CompletionCheckbox({
	isCompleted,
	isIndeterminate = false,
	isLocked = false,
	onClick,
	variant = "default",
}) {
	// Map variants to colors following the styling guide
	const variantColors = {
		default: "text-emerald-500",
		course: "text-teal-600", // Following styling guide
		book: "text-blue-600",
		video: "text-violet-600",
		flashcard: "text-amber-600",
	};

	const completedColor = variantColors[variant] || variantColors.default;

	const renderIcon = () => {
		if (isIndeterminate) {
			return <MinusSquare className={`w-5 h-5 ${completedColor}`} />;
		}
		if (isCompleted) {
			return <CheckCircle className={`w-5 h-5 ${completedColor}`} />;
		}
		return (
			<Circle
				className={`w-5 h-5 ${
					isLocked ? "text-zinc-200" : "text-zinc-300 hover:text-zinc-400"
				}`}
			/>
		);
	};

	return (
		<button
			type="button"
			onClick={(e) => {
				e.stopPropagation();
				if (!isLocked && onClick) {
					onClick(e);
				}
			}}
			className="mt-0.5 transition-all duration-200 hover:scale-110 hover:bg-zinc-50 rounded-full p-1 -m-1"
			disabled={isLocked}
		>
			{renderIcon()}
		</button>
	);
}

export default CompletionCheckbox;
