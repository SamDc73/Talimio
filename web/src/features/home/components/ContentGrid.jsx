import { AnimatePresence } from "framer-motion";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/button";
import EmptyState from "./EmptyState";
import SkeletonGrid from "./SkeletonGrid";

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
	onCreateFlashcards,
	_progressLoading,
}) {
	return (
		<>
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
				{isLoading ? (
					<SkeletonGrid count={6} />
				) : filteredAndSortedContent.length > 0 ? (
					<AnimatePresence mode="popLayout">
						{visible.map(renderCard)}
					</AnimatePresence>
				) : (
					<EmptyState
						onGenerateCourse={onGenerateCourse}
						onUploadBook={onUploadBook}
						onAddYoutube={onAddYoutube}
						onCreateFlashcards={onCreateFlashcards}
					/>
				)}
			</div>

			{!isLoading && unpinned.length > 3 && (
				<div className="mt-6 text-center">
					<Button
						variant="outline"
						onClick={onShowMoreToggle}
						className="h-10 min-w-[120px] flex items-center gap-2"
					>
						{showAll ? (
							<>
								<ChevronUp className="h-4 w-4" />
								Show Less
							</>
						) : (
							<>
								<ChevronDown className="h-4 w-4" />
								See {unpinned.length - 3} More
							</>
						)}
					</Button>
				</div>
			)}

			{!isLoading && filteredAndSortedContent.length === 0 && (
				<div className="text-center py-12">
					<div className="inline-block bg-emerald-50 p-4 rounded-full mb-4">
						<Check className="h-8 w-8 text-emerald-600" />
					</div>
					<h3 className="text-xl font-display font-bold text-emerald-700 mb-2">
						All Caught Up!
					</h3>
					<p className="text-muted-foreground">
						You've completed all your learning tasks. Great job!
					</p>
				</div>
			)}
		</>
	);
}
