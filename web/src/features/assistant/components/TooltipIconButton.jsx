"use client"

import { TooltipButton } from "@/components/TooltipButton"

export function TooltipIconButton({ tooltip, side = "bottom", children, ref, ...rest }) {
	return (
		<TooltipButton ref={ref} tooltipContent={tooltip} tooltipSide={side} variant="ghost" size="icon" {...rest}>
			{children}
		</TooltipButton>
	)
}
