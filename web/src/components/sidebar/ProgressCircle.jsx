/**
 * Circular progress indicator component
 * Shows completion percentage as a circle around a number with contextual colors following styling guide
 * @param {string} variant - Content type variant: 'course', 'book', 'video'
 */
function ProgressCircle({ number, progress, variant = "default" }) {
	// Map variants to stroke colors following the styling guide
	const strokeColors = {
		default: "var(--color-primary)",
		course: "var(--color-course)",
		book: "var(--color-book)",
		video: "var(--color-video)",
	}

	const strokeColor = strokeColors[variant] || strokeColors.default

	if (progress <= 0) {
		return (
			<div className="flex size-8 items-center justify-center rounded-full bg-muted/60">
				<span className="text-sm text-muted-foreground">{number}</span>
			</div>
		)
	}

	return (
		<div className="relative flex items-center justify-center">
			<div className="flex size-8 items-center justify-center rounded-full bg-muted/60">
				<span className="text-sm text-muted-foreground">{number}</span>
			</div>
			<svg
				className="absolute top-0 left-0 size-8  -rotate-90"
				role="img"
				aria-label={`Progress: ${Math.round(progress)}%`}
			>
				<title>Progress indicator</title>
				<circle cx="16" cy="16" r="14" strokeWidth="2.5" fill="none" stroke="var(--color-border)" className="opacity-70" />
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
				/>
			</svg>
		</div>
	)
}

export default ProgressCircle
