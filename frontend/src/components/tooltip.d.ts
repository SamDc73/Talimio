import type * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ComponentPropsWithoutRef, ElementRef, ReactNode } from "react";

export interface TooltipProps
	extends ComponentPropsWithoutRef<typeof TooltipPrimitive.Root> {
	children: ReactNode;
}

export interface TooltipContentProps
	extends ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> {
	sideOffset?: number;
	className?: string;
	children: ReactNode;
}

declare const TooltipProvider: typeof TooltipPrimitive.Provider;
declare const Tooltip: typeof TooltipPrimitive.Root;
declare const TooltipTrigger: typeof TooltipPrimitive.Trigger;
declare const TooltipContent: React.ForwardRefExoticComponent<
	TooltipContentProps &
		React.RefAttributes<ElementRef<typeof TooltipPrimitive.Content>>
>;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
