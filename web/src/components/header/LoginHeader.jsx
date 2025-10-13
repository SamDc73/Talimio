import { useMemo } from "react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"

// Logo Component
/**
 * @param {Object} props
 * @param {string} [props.className]
 * @param {"sm" | "md" | "lg"} [props.size="md"]
 * @param {string} [props.href="/"]
 * @returns {JSX.Element}
 */
export function LoginLogo({ className, size = "md", href = "/" }) {
	const sizeClasses = {
		sm: "h-8",
		md: "h-9",
		lg: "h-10",
	}

	// Compute size values to avoid nested ternaries
	const imageDimensions = useMemo(() => {
		if (size === "sm") return 24
		if (size === "md") return 32
		return 40
	}, [size])

	const textSize = useMemo(() => {
		if (size === "sm") return "text-lg"
		if (size === "md") return "text-xl"
		return "text-2xl"
	}, [size])

	return (
		<Link to={href} className={cn("flex items-center gap-2", className)}>
			<div className="relative">
				<img
					src="/logo.png"
					alt="Talimio Logo"
					width={imageDimensions}
					height={imageDimensions}
					className={cn("object-contain", sizeClasses[size])}
				/>
			</div>
			<span className={cn("font-bold tracking-tight text-foreground dark:text-white", textSize)}>
				Tali
				<span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 via-orange-500 to-cyan-500">
					mio
				</span>
			</span>
		</Link>
	)
}

// Login Header Component
/**
 * @param {Object} props
 * @param {string} [props.className]
 * @returns {JSX.Element}
 */
export function LoginHeader({ className }) {
	return (
		<header className={cn("fixed top-0 left-0 right-0 z-50 transition-all duration-300", className)}>
			<div className="container mx-auto px-4">
				<div className="flex h-16 items-center justify-between">
					{/* Logo - positioned exactly like in MainHeader */}
					<LoginLogo />
				</div>
			</div>
		</header>
	)
}
