import { useEffect } from "react"

import { Button } from "./button"

/**
 * TooltipButton - A wrapper component that safely combines Button with Tooltip
 * This avoids the React 19 + Radix UI ref composition issues
 */
function TooltipButton({
	children,
	tooltipContent,
	tooltipSide = "top",
	tooltipDelayDuration = 0,
	disableTooltip = false,
	ref,
	...buttonProps
}) {
	// Debug logging for ref issues
	useEffect(() => {
		if (ref && typeof ref === "object" && ref.current) {
		}
	}, [ref])

	// TEMPORARY: Always return just the button to diagnose the issue
	// TODO: Re-enable tooltips after fixing the ref composition issue
	return (
		<Button ref={ref} title={tooltipContent} {...buttonProps}>
			{children}
		</Button>
	)

	// Original tooltip code commented out for debugging
	/*
	// If tooltip is disabled or no content, return just the button
	if (disableTooltip || !tooltipContent) {
		return (
			<Button ref={ref} {...buttonProps}>
				{children}
			</Button>
		);
	}

	return (
		<TooltipProvider>
			<Tooltip delayDuration={tooltipDelayDuration}>
				<TooltipTrigger asChild>
					<Button ref={ref} {...buttonProps}>
						{children}
					</Button>
				</TooltipTrigger>
				<TooltipContent side={tooltipSide}>{tooltipContent}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
	*/
}

export { TooltipButton }
