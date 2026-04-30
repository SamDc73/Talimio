import * as DialogPrimitive from "@radix-ui/react-dialog"
import { DialogHeader } from "@/components/Dialog"
import { cn } from "@/lib/utils"

const ICON_TONE_CLASS_NAMES = {
	book: "text-(--color-book)",
	course: "text-(--color-course)",
	video: "text-(--color-video)",
}

export function DialogIconHeader({ title, icon: Icon, tone, wideLogo = false }) {
	const toneClassName = ICON_TONE_CLASS_NAMES[tone]

	return (
		<DialogHeader className="space-y-sm">
			<div className="flex items-center gap-sm">
				<Icon className={cn(wideLogo ? "h-lg w-auto" : "size-lg", "shrink-0", toneClassName)} />
				<DialogPrimitive.Title className="heading-bold">{title}</DialogPrimitive.Title>
			</div>
		</DialogHeader>
	)
}
