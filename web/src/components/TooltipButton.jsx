import { forwardRef } from "react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/**
 * TooltipButton - A button with sexy, subtle tooltip that appears on hover
 * Optimized for FAB positioning with left-side tooltips
 */
const TooltipButton = forwardRef(function TooltipButton(
	{
		children,
		tooltipContent,
		tooltipSide = "bottom",
		tooltipDelayDuration,
		disableTooltip = false,
		className,
		asChild = false,
		variant = "ghost",
		size = "icon",
		...buttonProps
	},
	ref
) {
	if (disableTooltip || !tooltipContent) {
		return (
			<Button ref={ref} className={className} asChild={asChild} variant={variant} size={size} {...buttonProps}>
				{children}
			</Button>
		)
	}

	return (
		<TooltipProvider delayDuration={tooltipDelayDuration}>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button ref={ref} className={cn(className)} asChild={asChild} variant={variant} size={size} {...buttonProps}>
						{children}
					</Button>
				</TooltipTrigger>
				<TooltipContent side={tooltipSide}>{tooltipContent}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	)
})

TooltipButton.displayName = "TooltipButton"

export { TooltipButton }
