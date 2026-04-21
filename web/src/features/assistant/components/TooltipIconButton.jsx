"use client"

import { Slottable } from "@radix-ui/react-slot"

import { Button } from "@/components/Button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/Tooltip"
import { cn } from "@/lib/utils"

export function TooltipIconButton({ children, tooltip, side = "bottom", className, ref, ...rest }) {
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
}
