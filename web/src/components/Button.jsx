import { Slot } from "@radix-ui/react-slot"

import { cn } from "@/lib/utils"
import { buttonVariants } from "./buttonVariants"

function Button({ className, variant, size, asChild = false, ref, ...props }) {
	const Comp = asChild ? Slot : "button"
	return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
}

export { Button }
