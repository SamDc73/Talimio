import { cn } from "@/lib/utils"

export function MasteryCircle({ value, className }) {
	const percentage = Math.max(0, Math.min(value || 0, 100))

	const size = 16
	const strokeWidth = 2
	const radius = (size - strokeWidth) / 2
	const circumference = 2 * Math.PI * radius
	const offset = circumference - (percentage / 100) * circumference

	return (
		<svg
			width={size}
			height={size}
			viewBox={`0 0 ${size} ${size}`}
			className={cn("shrink-0", className)}
			role="img"
			aria-label={`${percentage}% mastery`}
		>
			<circle
				cx={size / 2}
				cy={size / 2}
				r={radius}
				fill="none"
				stroke="currentColor"
				strokeWidth={strokeWidth}
				className="opacity-20"
			/>
			<circle
				cx={size / 2}
				cy={size / 2}
				r={radius}
				fill="none"
				stroke="currentColor"
				strokeWidth={strokeWidth}
				strokeDasharray={circumference}
				strokeDashoffset={offset}
				strokeLinecap="round"
				transform={`rotate(-90 ${size / 2} ${size / 2})`}
				className="transition-all duration-300"
			/>
		</svg>
	)
}
