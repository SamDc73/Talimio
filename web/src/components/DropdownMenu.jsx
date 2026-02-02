"use client"

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { Check, ChevronRight, Circle } from "lucide-react"

import { cn } from "@/lib/utils"

const DropdownMenu = DropdownMenuPrimitive.Root

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger

const DropdownMenuGroup = DropdownMenuPrimitive.Group

const DropdownMenuPortal = DropdownMenuPrimitive.Portal

const DropdownMenuSub = DropdownMenuPrimitive.Sub

const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup

function DropdownMenuSubTrigger({ className, inset, children, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.SubTrigger
			ref={ref}
			className={cn(
				"flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-muted data-[state=open]:bg-muted/40",
				inset && "pl-8",
				className
			)}
			{...props}
		>
			{children}
			<ChevronRight className="ml-auto size-4 " />
		</DropdownMenuPrimitive.SubTrigger>
	)
}

function DropdownMenuSubContent({ className, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.SubContent
			ref={ref}
			className={cn(
				"z-50 min-w-32 overflow-hidden rounded-md border bg-background p-1 text-foreground shadow-lg",
				className
			)}
			{...props}
		/>
	)
}

function DropdownMenuContent({ className, sideOffset = 4, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.Portal>
			<DropdownMenuPrimitive.Content
				ref={ref}
				sideOffset={sideOffset}
				className={cn(
					"z-50 min-w-32 overflow-hidden rounded-md border bg-background p-1 text-foreground shadow-md",
					className
				)}
				{...props}
			/>
		</DropdownMenuPrimitive.Portal>
	)
}

function DropdownMenuItem({ className, inset, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.Item
			ref={ref}
			className={cn(
				"relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-muted focus:text-foreground data-disabled:pointer-events-none data-disabled:opacity-50",
				inset && "pl-8",
				className
			)}
			{...props}
		/>
	)
}

function DropdownMenuCheckboxItem({ className, children, checked, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.CheckboxItem
			ref={ref}
			className={cn(
				"relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-muted focus:text-foreground data-disabled:pointer-events-none data-disabled:opacity-50",
				className
			)}
			checked={checked}
			{...props}
		>
			<span className="absolute left-2 flex size-3.5  items-center justify-center">
				<DropdownMenuPrimitive.ItemIndicator>
					<Check className="size-4 " />
				</DropdownMenuPrimitive.ItemIndicator>
			</span>
			{children}
		</DropdownMenuPrimitive.CheckboxItem>
	)
}

function DropdownMenuRadioItem({ className, children, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.RadioItem
			ref={ref}
			className={cn(
				"relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-muted focus:text-foreground data-disabled:pointer-events-none data-disabled:opacity-50",
				className
			)}
			{...props}
		>
			<span className="absolute left-2 flex size-3.5  items-center justify-center">
				<DropdownMenuPrimitive.ItemIndicator>
					<Circle className="size-2  fill-current" />
				</DropdownMenuPrimitive.ItemIndicator>
			</span>
			{children}
		</DropdownMenuPrimitive.RadioItem>
	)
}

function DropdownMenuLabel({ className, inset, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.Label
			ref={ref}
			className={cn("px-2 py-1.5 text-sm font-semibold", inset && "pl-8", className)}
			{...props}
		/>
	)
}

function DropdownMenuSeparator({ className, ref, ...props }) {
	return (
		<DropdownMenuPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted/40", className)} {...props} />
	)
}

function DropdownMenuShortcut({ className, ...props }) {
	return <span className={cn("ml-auto text-xs tracking-widest opacity-60", className)} {...props} />
}

export {
	DropdownMenu,
	DropdownMenuTrigger,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuCheckboxItem,
	DropdownMenuRadioItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuShortcut,
	DropdownMenuGroup,
	DropdownMenuPortal,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuRadioGroup,
}
