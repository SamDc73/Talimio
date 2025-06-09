import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, CheckCircle } from "lucide-react";
import { ContentRenderer } from "./ContentRenderer";
import "./LessonViewer.css";

/**
 * Component to display a lesson
 *
 * @param {Object} props
 * @param {Object} props.lesson - The lesson to display
 * @param {boolean} props.isLoading - Whether the lesson is loading
 * @param {string} props.error - Error message if any
 * @param {Function} props.onBack - Function to call when back button is clicked
 * @param {boolean} props.isDarkMode - Whether dark mode is enabled
 * @returns {JSX.Element}
 */
export function LessonViewer({
	lesson,
	isLoading,
	error,
	onBack,
	isDarkMode = false,
}) {
	// Handle loading state
	if (isLoading) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-zinc-500">
					<div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500 mb-4" />
					<p>Loading lesson...</p>
				</div>
			</div>
		);
	}

	// Handle error state
	if (error) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-red-600">
					<div className="max-w-3xl mx-auto p-6 bg-red-50 rounded-lg border border-red-200">
						<h2 className="text-xl font-semibold mb-4">Error loading lesson</h2>
						<p className="mb-4">{error}</p>
						<Button
							onClick={onBack}
							variant="outline"
							className="flex items-center gap-2"
						>
							<ArrowLeft className="w-4 h-4" />
							Back to outline
						</Button>
					</div>
				</div>
			</div>
		);
	}

	// Handle no lesson state
	if (!lesson) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-zinc-500">
					<div className="max-w-3xl mx-auto p-6 bg-zinc-50 rounded-lg border border-zinc-200">
						<h2 className="text-xl font-semibold mb-4">No lesson selected</h2>
						<p className="mb-4">
							Please select a lesson from the outline to view its content.
						</p>
						<Button
							onClick={onBack}
							variant="outline"
							className="flex items-center gap-2"
						>
							<ArrowLeft className="w-4 h-4" />
							Back to outline
						</Button>
					</div>
				</div>
			</div>
		);
	}

	// Render the lesson content
	return (
		<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
			<div className="max-w-4xl w-full mx-auto px-4 flex justify-center">
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					className={cn(
						"w-full rounded-xl border shadow-sm flex flex-col my-8",
						isDarkMode
							? "bg-zinc-900 border-zinc-800"
							: "bg-white border-zinc-200",
					)}
				>
					{/* Lesson header */}
					<div
						className={cn(
							"border-b p-6",
							isDarkMode
								? "border-zinc-800 bg-gradient-to-r from-emerald-900/20 to-teal-900/20"
								: "border-zinc-200 bg-gradient-to-r from-emerald-50 to-teal-50",
						)}
					>
						<div className="flex items-center gap-2 mb-4">
							<button
								type="button"
								onClick={onBack}
								className={cn(
									"flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
									isDarkMode
										? "bg-emerald-900/30 text-emerald-400 hover:bg-emerald-900/50"
										: "bg-emerald-100 text-emerald-700 hover:bg-emerald-200",
								)}
							>
								<ArrowLeft className="w-4 h-4" /> Back to Course
							</button>

							<div
								className={cn(
									"flex items-center text-sm",
									isDarkMode ? "text-zinc-400" : "text-zinc-500",
								)}
							>
								<span className="mx-2">•</span>
								<span>Module {lesson.moduleId || 1}</span>
								<span className="mx-2">•</span>
								<span>5 min read</span>
							</div>
						</div>
						<h1
							className={cn(
								"text-2xl font-bold",
								isDarkMode ? "text-white" : "text-zinc-900",
							)}
						>
							{lesson.title}
						</h1>
						<div className="flex items-center gap-2 mt-2">
							<span
								className={cn(
									"text-sm",
									isDarkMode ? "text-zinc-400" : "text-zinc-500",
								)}
							>
								Module {lesson.moduleId || 1}
							</span>
							<span
								className={cn(
									"text-sm",
									isDarkMode ? "text-zinc-600" : "text-zinc-400",
								)}
							>
								•
							</span>
							<span
								className={cn(
									"text-sm",
									isDarkMode ? "text-zinc-400" : "text-zinc-500",
								)}
							>
								5 min read
							</span>
						</div>
					</div>

					{/* Lesson content */}
					<div
						className={cn(
							"p-6 md:p-8 prose prose-lg max-w-none",
							isDarkMode ? "prose-invert prose-emerald" : "prose-emerald",
						)}
					>
						<ContentRenderer content={lesson.md_source} />
					</div>

					{/* Lesson navigation */}
					<div
						className={cn(
							"border-t p-4 flex items-center justify-between",
							isDarkMode
								? "border-zinc-800 bg-zinc-800/50"
								: "border-zinc-200 bg-zinc-50",
						)}
					>
						<div>
							<button
								type="button"
								onClick={onBack}
								className={cn(
									"flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-md transition-colors",
									isDarkMode
										? "bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
										: "bg-zinc-100 text-zinc-700 hover:bg-zinc-200",
								)}
							>
								<ArrowLeft className="w-4 h-4" /> Previous Lesson
							</button>
						</div>
						<div className="flex gap-4">
							<button
								type="button"
								onClick={onBack}
								className={cn(
									"flex items-center gap-1 px-4 py-2 text-sm font-medium text-white rounded-md transition-colors",
									isDarkMode
										? "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
										: "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600",
								)}
							>
								Next Lesson <ArrowRight className="w-4 h-4" />
							</button>
						</div>
					</div>
				</motion.div>
			</div>
		</div>
	);
}
