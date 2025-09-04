import { cva } from "class-variance-authority"

export const badgeVariants = cva(
	"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2",
	{
		variants: {
			variant: {
				default: "border-transparent bg-green-500 text-white hover:bg-green-500/80",
				secondary: "border-transparent bg-gray-100 text-gray-900 hover:bg-gray-100/80",
				destructive: "border-transparent bg-red-500 text-red-500-foreground hover:bg-red-500/80",
				outline: "text-gray-900",
			},
		},
		defaultVariants: {
			variant: "default",
		},
	}
)
