import * as SheetPrimitive from "@radix-ui/react-dialog"
import { cva } from "class-variance-authority"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

const Sheet = SheetPrimitive.Root
const SheetTrigger = SheetPrimitive.Trigger
const SheetClose = SheetPrimitive.Close
const SheetPortal = SheetPrimitive.Portal

function SheetOverlay({ className, ref, ...props }) {
	return (
		<SheetPrimitive.Overlay
			className={cn("fixed inset-0 z-50 bg-background/80 backdrop-blur-sm", className)}
			{...props}
			ref={ref}
		/>
	)
}

const sheetVariants = cva("fixed z-50 gap-4 bg-background p-6 shadow-lg", {
	variants: {
		side: {
			top: "inset-x-0 top-0 border-b",
			bottom: "inset-x-0 bottom-0 border-t",
			left: "inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm",
			right: "inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm",
		},
	},
	defaultVariants: {
		side: "right",
	},
})

function SheetContent({ side = "right", className, children, ref, ...props }) {
	return (
		<SheetPortal>
			<SheetOverlay />
			<SheetPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
				{children}
				<SheetPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-muted">
					<X className="size-4 " />
					<span className="sr-only">Close</span>
				</SheetPrimitive.Close>
			</SheetPrimitive.Content>
		</SheetPortal>
	)
}

function SheetHeader({ className, ...props }) {
	return <div className={cn("flex flex-col space-y-2 text-center sm:text-left", className)} {...props} />
}

function SheetFooter({ className, ...props }) {
	return <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
}

function SheetTitle({ className, ref, ...props }) {
	return (
		<SheetPrimitive.Title ref={ref} className={cn("text-lg font-semibold text-foreground", className)} {...props} />
	)
}

function SheetDescription({ className, ref, ...props }) {
	return <SheetPrimitive.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
}

export {
	Sheet,
	SheetPortal,
	SheetOverlay,
	SheetTrigger,
	SheetClose,
	SheetContent,
	SheetHeader,
	SheetFooter,
	SheetTitle,
	SheetDescription,
}
