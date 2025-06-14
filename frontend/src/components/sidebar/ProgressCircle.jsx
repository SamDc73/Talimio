/**
 * Circular progress indicator component
 * Shows completion percentage as a circle around a number
 * @param {string} variant - Content type variant: 'course', 'book', 'video', 'flashcard'
 */
function ProgressCircle({ number, progress, variant = "default" }) {
	// Map variants to stroke colors
	const strokeColors = {
		default: "#10b981", // emerald-500
		course: "hsl(var(--course-bg))",
		book: "hsl(var(--book-bg))",
		video: "hsl(var(--video-bg))",
		flashcard: "hsl(var(--flashcard-bg))",
	};

	const strokeColor = strokeColors[variant] || strokeColors.default;
	if (progress <= 0) {
		return (
			<div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center">
				<span className="text-sm text-zinc-600">{number}</span>
			</div>
		);
	}

	return (
		<div className="relative flex items-center justify-center">
			<div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center">
				<span className="text-sm text-zinc-600">{number}</span>
			</div>
			<svg
				className="absolute top-0 left-0 w-8 h-8 -rotate-90"
				role="img"
				aria-label={`Progress: ${Math.round(progress)}%`}
			>
				<title>Progress indicator</title>
				<circle
					cx="16"
					cy="16"
					r="14"
					strokeWidth="2.5"
					fill="none"
					stroke="#f4f4f5"
					className="opacity-70"
				/>
				<circle
					cx="16"
					cy="16"
					r="14"
					strokeWidth="2.5"
					fill="none"
					stroke={strokeColor}
					strokeLinecap="round"
					strokeDasharray={`${(progress / 100) * 87.96} 87.96`}
					className="transition-all duration-300"
					style={{
						filter: "drop-shadow(0 1px 1px rgb(0 0 0 / 0.05))",
					}}
				/>
			</svg>
		</div>
	);
}

export default ProgressCircle;
