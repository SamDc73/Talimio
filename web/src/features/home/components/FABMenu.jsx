import { AnimatePresence, motion } from "framer-motion"
import { BookOpen, Layers, Plus, Sparkles, Youtube } from "lucide-react"
import { Button } from "@/components/button"
import { TooltipButton } from "@/components/TooltipButton"

export default function FABMenu({
	isFabExpanded,
	onToggleExpanded,
	onGenerateRoadmap,
	onUploadBook,
	onAddYoutube,
	onCreateFlashcards,
}) {
	return (
		<div className="fixed bottom-8 right-8 z-50">
			<AnimatePresence>
				{isFabExpanded && (
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: 20 }}
						transition={{ duration: 0.2 }}
						className="flex flex-col items-center gap-3 mb-4"
					>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
							onClick={() => {
								onGenerateRoadmap()
								onToggleExpanded()
							}}
							tooltipContent="Generate Course"
							tooltipSide="left"
						>
							<Sparkles className="h-6 w-6" />
						</TooltipButton>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
							onClick={() => {
								onUploadBook()
								onToggleExpanded()
							}}
							tooltipContent="Upload Book"
							tooltipSide="left"
						>
							<BookOpen className="h-6 w-6" />
						</TooltipButton>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
							onClick={() => {
								onAddYoutube()
								onToggleExpanded()
							}}
							tooltipContent="Add YouTube Video"
							tooltipSide="left"
						>
							<Youtube className="h-6 w-6" />
						</TooltipButton>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
							onClick={() => {
								onCreateFlashcards()
								onToggleExpanded()
							}}
							tooltipContent="Create Flashcards"
							tooltipSide="left"
						>
							<Layers className="h-6 w-6" />
						</TooltipButton>
					</motion.div>
				)}
			</AnimatePresence>
			<Button className="rounded-full h-16 w-16 shadow-lg" onClick={onToggleExpanded}>
				<motion.div animate={{ rotate: isFabExpanded ? 45 : 0 }} transition={{ duration: 0.3 }}>
					<Plus className={`h-8 w-8 transition-transform duration-300 ${isFabExpanded ? "rotate-45" : ""}`} />
				</motion.div>
			</Button>
		</div>
	)
}
