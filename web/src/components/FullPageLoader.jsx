import { cn } from "@/lib/utils"

export default function FullPageLoader({ message = "Loading...", offsetHeader = false, className }) {
	const minHeightClass = offsetHeader ? "min-h-[calc(100vh-4rem)]" : "min-h-screen"
	return (
		<div className={cn("flex w-full items-center justify-center", minHeightClass, className)}>
			<div className="text-lg">{message}</div>
		</div>
	)
}
