import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, Layers, Plus, Sparkles, Youtube } from "lucide-react";
import { Button } from "@/components/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tooltip";

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
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="secondary"
									className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
									onClick={() => {
										onGenerateRoadmap();
										onToggleExpanded();
									}}
								>
									<Sparkles className="h-6 w-6" />
								</Button>
							</TooltipTrigger>
							<TooltipContent side="left">
								<p>Generate Course</p>
							</TooltipContent>
						</Tooltip>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="secondary"
									className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
									onClick={() => {
										onUploadBook();
										onToggleExpanded();
									}}
								>
									<BookOpen className="h-6 w-6" />
								</Button>
							</TooltipTrigger>
							<TooltipContent side="left">
								<p>Upload Book</p>
							</TooltipContent>
						</Tooltip>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="secondary"
									className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
									onClick={() => {
										onAddYoutube();
										onToggleExpanded();
									}}
								>
									<Youtube className="h-6 w-6" />
								</Button>
							</TooltipTrigger>
							<TooltipContent side="left">
								<p>Add YouTube Video</p>
							</TooltipContent>
						</Tooltip>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="secondary"
									className="rounded-full h-14 w-14 shadow-lg flex items-center justify-center gap-2"
									onClick={() => {
										onCreateFlashcards();
										onToggleExpanded();
									}}
								>
									<Layers className="h-6 w-6" />
								</Button>
							</TooltipTrigger>
							<TooltipContent side="left">
								<p>Create Flashcards</p>
							</TooltipContent>
						</Tooltip>
					</motion.div>
				)}
			</AnimatePresence>
			<Button
				className="rounded-full h-16 w-16 shadow-lg"
				onClick={onToggleExpanded}
			>
				<motion.div
					animate={{ rotate: isFabExpanded ? 45 : 0 }}
					transition={{ duration: 0.3 }}
				>
					<Plus
						className={`h-8 w-8 transition-transform duration-300 ${isFabExpanded ? "rotate-45" : ""}`}
					/>
				</motion.div>
			</Button>
		</div>
	);
}
