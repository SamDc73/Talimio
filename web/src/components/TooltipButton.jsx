import { AnimatePresence, motion } from "framer-motion"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { Button } from "./button"

/**
 * TooltipButton - A button with sexy, subtle tooltip that appears on hover
 * Optimized for FAB positioning with left-side tooltips
 */
function TooltipButton({
	children,
	tooltipContent,
	tooltipSide = "left",
	tooltipDelayDuration = 300,
	disableTooltip = false,
	className,
	...buttonProps
}) {
	const [isVisible, setIsVisible] = useState(false)
	const [timeoutId, setTimeoutId] = useState(null)

	const showTooltip = () => {
		if (disableTooltip || !tooltipContent) return

		if (timeoutId) clearTimeout(timeoutId)
		const id = setTimeout(() => setIsVisible(true), tooltipDelayDuration)
		setTimeoutId(id)
	}

	const hideTooltip = () => {
		if (timeoutId) {
			clearTimeout(timeoutId)
			setTimeoutId(null)
		}
		setIsVisible(false)
	}

	// Cleanup timeout on unmount
	useEffect(() => {
		return () => {
			if (timeoutId) {
				clearTimeout(timeoutId)
			}
		}
	}, [timeoutId])

	// If tooltip is disabled or no content, return just the button
	if (disableTooltip || !tooltipContent) {
		return (
			<Button className={className} {...buttonProps}>
				{children}
			</Button>
		)
	}

	// Tooltip positioning classes based on side
	const tooltipPositionClasses = {
		left: "right-full mr-3 top-1/2 -translate-y-1/2",
		right: "left-full ml-3 top-1/2 -translate-y-1/2",
		top: "bottom-full mb-3 left-1/2 -translate-x-1/2",
		bottom: "top-full mt-3 left-1/2 -translate-x-1/2",
	}

	// Animation variants for smooth entrance
	const tooltipVariants = {
		hidden: {
			opacity: 0,
			scale: 0.95,
			x: tooltipSide === "left" ? 8 : tooltipSide === "right" ? -8 : 0,
			y: tooltipSide === "top" ? 8 : tooltipSide === "bottom" ? -8 : 0,
		},
		visible: {
			opacity: 1,
			scale: 1,
			x: 0,
			y: 0,
			transition: {
				type: "spring",
				stiffness: 400,
				damping: 25,
				duration: 0.2,
			},
		},
		exit: {
			opacity: 0,
			scale: 0.95,
			x: tooltipSide === "left" ? 8 : tooltipSide === "right" ? -8 : 0,
			y: tooltipSide === "top" ? 8 : tooltipSide === "bottom" ? -8 : 0,
			transition: { duration: 0.15 },
		},
	}

	return (
		<div className="relative inline-block">
			<Button className={className} onMouseEnter={showTooltip} onMouseLeave={hideTooltip} {...buttonProps}>
				{children}
			</Button>

			<AnimatePresence>
				{isVisible && (
					<motion.div
						initial="hidden"
						animate="visible"
						exit="exit"
						variants={tooltipVariants}
						className={cn("absolute z-50 pointer-events-none whitespace-nowrap", tooltipPositionClasses[tooltipSide])}
					>
						{/* Sexy tooltip with gradient background and glass effect */}
						<div className="relative">
							{/* Main tooltip content */}
							<div className="bg-popover/95 backdrop-blur-sm border border-border/50 rounded-xl px-4 py-2.5 shadow-2xl">
								<div className="text-sm font-medium text-popover-foreground tracking-wide">{tooltipContent}</div>
							</div>

							{/* Subtle arrow pointing to button */}
							{tooltipSide === "left" && (
								<div className="absolute top-1/2 -translate-y-1/2 -right-1 w-2 h-2 bg-popover/95 border-r border-b border-border/50 rotate-45" />
							)}
							{tooltipSide === "right" && (
								<div className="absolute top-1/2 -translate-y-1/2 -left-1 w-2 h-2 bg-popover/95 border-l border-t border-border/50 rotate-45" />
							)}
							{tooltipSide === "top" && (
								<div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-popover/95 border-b border-l border-border/50 rotate-45" />
							)}
							{tooltipSide === "bottom" && (
								<div className="absolute left-1/2 -translate-x-1/2 -top-1 w-2 h-2 bg-popover/95 border-t border-r border-border/50 rotate-45" />
							)}
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</div>
	)
}

export { TooltipButton }
