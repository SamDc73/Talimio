"use client"

import { Slottable } from "@radix-ui/react-slot"
import { forwardRef } from "react"
import { Button } from "@/components/Button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import { cn } from "@/lib/utils"

export const TooltipIconButton = forwardRef(function TooltipIconButton(
	{ children, tooltip, side = "bottom", className, ...rest },
	ref
) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button variant="ghost" size="icon" {...rest} className={cn("aui-button-icon size-6 p-1", className)} ref={ref}>
					<Slottable>{children}</Slottable>
					<span className="aui-sr-only sr-only">{tooltip}</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side={side}>{tooltip}</TooltipContent>
		</Tooltip>
	)
})
