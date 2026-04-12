import { Loader2, RotateCcw } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/Button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/Dialog"

const MIN_CRITIQUE_LENGTH = 10

export function RegenerateModal({ open, onOpenChange, onRegenerate, isRegenerating = false }) {
	const [critique, setCritique] = useState("")
	const textareaRef = useRef(null)
	const trimmedCritiqueLength = critique.trim().length
	const remainingCharacters = Math.max(0, MIN_CRITIQUE_LENGTH - trimmedCritiqueLength)

	const canSubmit = trimmedCritiqueLength >= MIN_CRITIQUE_LENGTH && !isRegenerating

	useEffect(() => {
		if (!open || isRegenerating) {
			return
		}

		const focusHandle = window.setTimeout(() => {
			textareaRef.current?.focus()
		}, 40)

		return () => window.clearTimeout(focusHandle)
	}, [isRegenerating, open])

	const handleSubmit = useCallback(
		(e) => {
			e?.preventDefault()
			if (!canSubmit) return
			void onRegenerate(critique.trim())
		},
		[canSubmit, critique, onRegenerate]
	)

	const handleOpenChange = useCallback(
		(nextOpen) => {
			if (isRegenerating) return
			if (!nextOpen) {
				setCritique("")
			}
			onOpenChange(nextOpen)
		},
		[isRegenerating, onOpenChange]
	)

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="gap-5 sm:max-w-[560px]">
				<form onSubmit={handleSubmit} className="space-y-5">
					<DialogHeader className="space-y-2">
						<div className="flex items-center gap-3">
							<div className="rounded-lg bg-linear-to-br from-(--color-course)/90 to-(--color-course) p-2.5">
								<RotateCcw className="size-5 text-white" />
							</div>
							<DialogTitle className="text-2xl">Regenerate lesson</DialogTitle>
						</div>
						<p className="text-sm text-muted-foreground">
							Say what felt off and what you want changed. Keep it specific so the next version is actually different.
						</p>
					</DialogHeader>

					<div className="space-y-3">
						<fieldset className="relative flex flex-col rounded-xl border border-border bg-background shadow-sm transition-all duration-200 hover:border-muted-foreground/30 focus-within:border-(--color-course) focus-within:ring-4 focus-within:ring-(--color-course)/10">
							<textarea
								id="lesson-regenerate-critique"
								ref={textareaRef}
								value={critique}
								onChange={(e) => setCritique(e.target.value)}
								aria-label="Regeneration request"
								placeholder="e.g. Use simpler language and add one worked example."
								disabled={isRegenerating}
								rows={4}
								aria-invalid={trimmedCritiqueLength > 0 && trimmedCritiqueLength < MIN_CRITIQUE_LENGTH}
								className="min-h-[120px] w-full resize-none bg-transparent px-4 py-3 text-sm/relaxed placeholder:text-muted-foreground/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
							/>
						</fieldset>

						{trimmedCritiqueLength > 0 && trimmedCritiqueLength < MIN_CRITIQUE_LENGTH ? (
							<p className="text-xs text-muted-foreground">
								Add {remainingCharacters} more character{remainingCharacters === 1 ? "" : "s"}.
							</p>
						) : null}
					</div>

					<div className="flex justify-end gap-2.5 pt-1">
						<Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isRegenerating}>
							Cancel
						</Button>
						<Button
							type="submit"
							disabled={!canSubmit}
							className="min-w-[140px] bg-(--color-course) text-white hover:bg-(--color-course)/90"
						>
							{isRegenerating ? (
								<>
									<Loader2 className="size-4 animate-spin" />
									Regenerating...
								</>
							) : (
								"Regenerate"
							)}
						</Button>
					</div>
				</form>
			</DialogContent>
		</Dialog>
	)
}
