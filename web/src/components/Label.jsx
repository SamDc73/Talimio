"use client"

import * as LabelPrimitive from "@radix-ui/react-label"

import { cn } from "@/lib/utils"

const labelClassName = "text-sm/none font-medium  peer-disabled:cursor-not-allowed peer-disabled:opacity-70"

function Label({ className, children, ref, ...props }) {
	return (
		<LabelPrimitive.Root ref={ref} className={cn(labelClassName, className)} {...props}>
			{children}
		</LabelPrimitive.Root>
	)
}

export { Label }
