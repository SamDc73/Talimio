import { AnimatePresence } from "framer-motion"
import { Check, ChevronDown, ChevronUp } from "lucide-react"
import { Button } from "@/components/Button"
import EmptyState from "./EmptyState"
import SkeletonGrid from "./SkeletonGrid"

export default function ContentGrid({
	isLoading,
	filteredAndSortedContent,
	visible,
	unpinned,
	showAll,
	renderCard,
	onShowMoreToggle,
	onGenerateCourse,
	onUploadBook,
	onAddYoutube,
	_progressLoading,
}) {
	let gridContent = (
		<EmptyState onGenerateCourse={onGenerateCourse} onUploadBook={onUploadBook} onAddYoutube={onAddYoutube} />
	)
	if (isLoading) {
		gridContent = <SkeletonGrid count={6} />
	} else if (filteredAndSortedContent.length > 0) {
		gridContent = (
			<AnimatePresence mode="popLayout">{visible.map((item, index) => renderCard(item, index))}</AnimatePresence>
		)
	}

	return (
		<>
			<div className="grid grid-cols-1 gap-lg md:grid-cols-2 lg:grid-cols-3">{gridContent}</div>

			{!isLoading && unpinned.length > 3 && (
				<div className="mt-xl">
					<Button variant="outline" onClick={onShowMoreToggle} className="gap-2xs px-md py-2xs text-sm font-medium">
						{showAll ? (
							<>
								<ChevronUp className="size-4  -mt-px" />
								<span>Show Less</span>
							</>
						) : (
							<>
								<ChevronDown className="size-4  -mt-px" />
								<span>See {unpinned.length - 3} More</span>
							</>
						)}
					</Button>
				</div>
			)}

			{!isLoading && filteredAndSortedContent.length === 0 && (
				<div className="py-xl text-center">
					<div className="mb-md inline-block rounded-full bg-completed/10 p-md">
						<Check className="size-xl text-completed" />
					</div>
					<h3 className="mb-2xs text-xl font-bold text-completed">All Caught Up!</h3>
					<p className="text-muted-foreground">You've completed all your learning tasks. Great job!</p>
				</div>
			)}
		</>
	)
}
