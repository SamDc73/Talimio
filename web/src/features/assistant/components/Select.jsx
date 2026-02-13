"use client"

import * as SelectPrimitive from "@radix-ui/react-select"
import { cva } from "class-variance-authority"
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import { cn } from "@/lib/utils"

const SelectRoot = SelectPrimitive.Root

const selectTriggerVariants = cva(
	"flex w-fit items-center justify-between gap-2 whitespace-nowrap rounded-md text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-placeholder:text-muted-foreground [&>span]:line-clamp-1 [&_svg:not([class*='size-'])]:size-4 [&_svg]:pointer-events-none [&_svg]:shrink-0",
	{
		variants: {
			variant: {
				outline: "border border-input bg-transparent hover:bg-accent hover:text-accent-foreground",
				ghost: "hover:bg-accent hover:text-accent-foreground",
				muted: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
			},
			size: {
				default: "h-9 px-3 py-2",
				sm: "h-8 px-2.5 py-1.5 text-xs",
				lg: "h-10 px-4 py-2.5",
			},
		},
		defaultVariants: {
			variant: "outline",
			size: "default",
		},
	}
)

function SelectTrigger({ className, variant, size, children, ...props }) {
	return (
		<SelectPrimitive.Trigger
			data-slot="select-trigger"
			data-variant={variant ?? "outline"}
			data-size={size ?? "default"}
			className={cn(selectTriggerVariants({ variant, size }), className)}
			{...props}
		>
			{children}
			<SelectPrimitive.Icon asChild>
				<ChevronDownIcon className="size-4 opacity-50" />
			</SelectPrimitive.Icon>
		</SelectPrimitive.Trigger>
	)
}

function SelectScrollUpButton({ className, ...props }) {
	return (
		<SelectPrimitive.ScrollUpButton
			data-slot="select-scroll-up-button"
			className={cn("flex cursor-default items-center justify-center py-1", className)}
			{...props}
		>
			<ChevronUpIcon className="size-4" />
		</SelectPrimitive.ScrollUpButton>
	)
}

function SelectScrollDownButton({ className, ...props }) {
	return (
		<SelectPrimitive.ScrollDownButton
			data-slot="select-scroll-down-button"
			className={cn("flex cursor-default items-center justify-center py-1", className)}
			{...props}
		>
			<ChevronDownIcon className="size-4" />
		</SelectPrimitive.ScrollDownButton>
	)
}

function SelectContent({ className, children, position = "popper", ...props }) {
	return (
		<SelectPrimitive.Portal>
			<SelectPrimitive.Content
				data-slot="select-content"
				position={position}
				sideOffset={6}
				className={cn(
					"relative z-50 max-h-96 min-w-32 overflow-hidden rounded-xl border bg-popover/95 p-1.5 text-popover-foreground shadow-lg backdrop-blur-sm",
					"data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:animate-in",
					"data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:animate-out",
					"data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
					position === "popper" &&
						"data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1",
					className
				)}
				{...props}
			>
				<SelectScrollUpButton />
				<SelectPrimitive.Viewport
					className={cn(
						position === "popper" &&
							"h-(--radix-select-trigger-height) w-full min-w-(--radix-select-trigger-width) scroll-my-1"
					)}
				>
					{children}
				</SelectPrimitive.Viewport>
				<SelectScrollDownButton />
			</SelectPrimitive.Content>
		</SelectPrimitive.Portal>
	)
}

export { SelectRoot, SelectTrigger, SelectContent }
