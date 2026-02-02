import { AlertTriangle } from "lucide-react"

import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/Dialog"

export function ConfirmationDialog({
	open,
	onOpenChange,
	title = "Are you sure?",
	description = "This action cannot be undone.",
	confirmText = "Delete",
	cancelText = "Cancel",
	onConfirm,
	isDestructive = true,
	itemName = "",
}) {
	const handleConfirm = (e) => {
		e?.stopPropagation()
		onConfirm()
		onOpenChange(false)
	}

	const handleCancel = (e) => {
		e?.stopPropagation()
		onOpenChange(false)
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[425px]">
				<DialogHeader>
					<div className="flex items-center gap-3">
						{isDestructive && (
							<div className="flex size-10  items-center justify-center rounded-full bg-destructive/10">
								<AlertTriangle className="size-5  text-destructive" />
							</div>
						)}
						<div className="text-left">
							<DialogTitle className="text-lg font-semibold text-foreground">{title}</DialogTitle>
						</div>
					</div>
				</DialogHeader>
				<DialogDescription className="text-sm text-muted-foreground mt-2">
					{itemName ? (
						<>
							{description} <span className="font-medium">"{itemName}"</span> will be permanently removed.
						</>
					) : (
						description
					)}
				</DialogDescription>
				<DialogFooter className="gap-2 mt-6">
					<Button variant="outline" onClick={handleCancel} className="flex-1">
						{cancelText}
					</Button>
					<Button variant={isDestructive ? "destructive" : "default"} onClick={handleConfirm} className="flex-1">
						{confirmText}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	)
}
