import { cn } from "@/lib/utils"

const Card = ({ className, ref, ...props }) => (
	<div ref={ref} className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...props} />
)

const CardHeader = ({ className, ref, ...props }) => (
	<div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
)

const CardTitle = ({ className, ref, ...props }) => (
	<h3
		ref={ref}
		className={cn("text-2xl font-display font-semibold leading-none tracking-tight", className)}
		{...props}
	/>
)

const CardDescription = ({ className, ref, ...props }) => (
	<p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
)

const CardContent = ({ className, ref, ...props }) => <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />

const CardFooter = ({ className, ref, ...props }) => (
	<div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
)

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
