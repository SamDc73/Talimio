import { CheckCircle, Circle } from "lucide-react";

/**
 * Completion checkbox component for sidebar items
 * Shows either a checkmark or empty circle based on completion state
 */
function CompletionCheckbox({ isCompleted, isLocked = false, onClick }) {
	return (
		<button
			type="button"
			onClick={(e) => {
				e.stopPropagation();
				if (!isLocked && onClick) {
					onClick(e);
				}
			}}
			className="mt-0.5 transition-all duration-200 hover:scale-110"
			disabled={isLocked}
		>
			{isCompleted ? (
				<CheckCircle className="w-5 h-5 text-emerald-500" />
			) : (
				<Circle
					className={`w-5 h-5 ${
						isLocked ? "text-zinc-200" : "text-zinc-300 hover:text-emerald-300"
					}`}
				/>
			)}
		</button>
	);
}

export default CompletionCheckbox;
