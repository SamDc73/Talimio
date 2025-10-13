import { forwardRef } from "react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

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
	const button = (
		<Button ref={ref} className={className} asChild={asChild} variant={variant} size={size} {...buttonProps}>
			{children}
		</Button>
	)

	if (disableTooltip || !tooltipContent) {
		return button
	}

	const triggerChild = buttonProps.disabled ? <span className="inline-block">{button}</span> : button

	const tooltip = (
		<Tooltip>
			<TooltipTrigger asChild>{triggerChild}</TooltipTrigger>
			<TooltipContent side={tooltipSide}>{tooltipContent}</TooltipContent>
		</Tooltip>
	)

	const providerProps = {}
	if (typeof tooltipDelayDuration === "number") {
		providerProps.delayDuration = tooltipDelayDuration
	}

	return <TooltipProvider {...providerProps}>{tooltip}</TooltipProvider>
})

TooltipButton.displayName = "TooltipButton"

export { TooltipButton }
