export function CircularProgress({ value, size = 120, strokeWidth = 10, className = "" }) {
	const percentage = Math.round(value || 0)
	const radius = size / 2 - 10
	const circumference = Math.ceil(Math.PI * radius * 2)
	const offset = Math.ceil(circumference * ((100 - percentage) / 100))
	const viewBox = `-${size * 0.125} -${size * 0.125} ${size * 1.25} ${size * 1.25}`

	const getProgressColor = () => {
		if (percentage < 30) return { stroke: "stroke-green-500", glow: "rgba(34, 197, 94, 0.3)" }
		if (percentage < 70) return { stroke: "stroke-teal-500", glow: "rgba(20, 184, 166, 0.3)" }
		return { stroke: "stroke-blue-500", glow: "rgba(59, 130, 246, 0.3)" }
	}

	const colors = getProgressColor()

	return (
		<div className={`relative ${className}`.trim()}>
			<svg
				width={size}
				height={size}
				viewBox={viewBox}
				xmlns="http://www.w3.org/2000/svg"
				role="img"
				aria-label={`${percentage}% progress`}
				style={{
					transform: "rotate(-90deg)",
					filter: `drop-shadow(0 0 20px ${colors.glow})`,
				}}
			>
				<title>Learning Progress: {percentage}%</title>
				<circle
					r={radius}
					cx={size / 2}
					cy={size / 2}
					fill="transparent"
					strokeWidth={strokeWidth}
					strokeDasharray={circumference}
					strokeDashoffset="0"
					className="stroke-border/15"
				/>
				<circle
					r={radius}
					cx={size / 2}
					cy={size / 2}
					strokeWidth={strokeWidth}
					strokeLinecap="round"
					strokeDashoffset={offset}
					fill="transparent"
					strokeDasharray={circumference}
					className={colors.stroke}
					style={{
						transition: "stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.6s ease",
					}}
				/>
			</svg>
			<div className="absolute inset-0 flex items-center justify-center">
				<span className="text-4xl font-bold tabular-nums tracking-tighter">{percentage}%</span>
			</div>
		</div>
	)
}
