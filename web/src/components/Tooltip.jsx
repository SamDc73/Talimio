"use client"

import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { forwardRef } from "react"

import { cn } from "@/lib/utils"

// Export the provider directly; mount it once near the app root.
const TooltipProvider = TooltipPrimitive.Provider

// Root, Trigger, and Content primitives
const Tooltip = TooltipPrimitive.Root

const TooltipTrigger = forwardRef(function TooltipTrigger({ ...props }, ref) {
	return <TooltipPrimitive.Trigger ref={ref} data-slot="tooltip-trigger" {...props} />
})

TooltipTrigger.displayName = "TooltipTrigger"

function TooltipContent({ className, sideOffset = 0, children, ...props }) {
	return (
		<TooltipPrimitive.Portal>
			<TooltipPrimitive.Content
				data-slot="tooltip-content"
				sideOffset={sideOffset}
				className={cn(
					"bg-foreground text-background z-50 w-fit origin-(--radix-tooltip-content-transform-origin) rounded-md px-3 py-1.5 text-xs text-balance",
					className
				)}
				{...props}
			>
				{children}
				<TooltipPrimitive.Arrow className="bg-foreground fill-foreground z-50 size-2.5 translate-y-[calc(-50%-2px)] rotate-45 rounded-sm" />
			</TooltipPrimitive.Content>
		</TooltipPrimitive.Portal>
	)
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
