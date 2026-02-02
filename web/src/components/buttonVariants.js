import { cva } from "class-variance-authority"

export const buttonVariants = cva(
	// Base matches Liftkit spacing with slight roundness (rounded-md) everywhere
	"inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
	{
		variants: {
			variant: {
				default: "bg-primary text-primary-foreground hover:bg-primary/90",
				destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
				outline: "border border-border bg-background hover:bg-muted hover:text-foreground",
				secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
				ghost: "hover:bg-muted hover:text-foreground",
				link: "text-primary underline-offset-4 hover:underline",
			},
			size: {
				// Liftkit spacing: generous em-based padding (1em horizontal, calculated vertical)
				sm: "px-3.5 py-2 text-sm",
				default: "px-4 py-2.5 text-base",
				lg: "px-6 py-3.5 text-lg",
				icon: "size-10 ",
			},
		},
		defaultVariants: {
			variant: "default",
			size: "default",
		},
	}
)
