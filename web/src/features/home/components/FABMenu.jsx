import { AnimatePresence, motion } from "framer-motion"
import { BookOpen, Plus, Sparkles, Youtube } from "lucide-react"
import { TooltipButton } from "@/components/TooltipButton"

export default function FABMenu({ isFabExpanded, onToggleExpanded, onGenerateRoadmap, onUploadBook, onAddYoutube }) {
	return (
		<div className="fixed bottom-8 right-8 z-50">
			<AnimatePresence>
				{isFabExpanded && (
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: 20 }}
						transition={{ duration: 0.2 }}
						className="flex flex-col items-center gap-4 mb-6"
					>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 bg-course/10 hover:bg-course/20 border-course/20"
							onClick={() => {
								onGenerateRoadmap()
								onToggleExpanded()
							}}
							tooltipContent="Generate Course"
							tooltipSide="left"
							tooltipDelayDuration={200}
						>
							<Sparkles className="h-6 w-6 text-course" />
						</TooltipButton>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 bg-book/10 hover:bg-book/20 border-book/20"
							onClick={() => {
								onUploadBook()
								onToggleExpanded()
							}}
							tooltipContent="Upload Book"
							tooltipSide="left"
							tooltipDelayDuration={200}
						>
							<BookOpen className="h-6 w-6 text-book" />
						</TooltipButton>
						<TooltipButton
							variant="secondary"
							className="rounded-full h-14 w-14 shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 bg-video/10 hover:bg-video/20 border-video/20"
							onClick={() => {
								onAddYoutube()
								onToggleExpanded()
							}}
							tooltipContent="Add YouTube Video"
							tooltipSide="left"
							tooltipDelayDuration={200}
						>
							<Youtube className="h-6 w-6 text-video" />
						</TooltipButton>
					</motion.div>
				)}
			</AnimatePresence>
			<TooltipButton
				className="rounded-full h-16 w-16 shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 bg-primary hover:bg-primary/90"
				onClick={onToggleExpanded}
				tooltipContent={isFabExpanded ? "Close" : "Quick Actions"}
				tooltipSide="left"
				tooltipDelayDuration={200}
			>
				<motion.div animate={{ rotate: isFabExpanded ? 45 : 0 }} transition={{ duration: 0.3 }}>
					<Plus className="h-8 w-8 text-primary-foreground" />
				</motion.div>
			</TooltipButton>
		</div>
	)
}
