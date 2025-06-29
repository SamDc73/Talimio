import { ArrowLeft, CheckCircle, RotateCcw } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import { ContentRenderer } from "./ContentRenderer";
import "./LessonViewer.css";

/**
 * Simplified lesson viewer component
 */
export function LessonViewer({
	lesson,
	isLoading,
	error,
	onBack,
	onMarkComplete,
	onRegenerate,
	isDarkMode = false,
}) {
	// Loading state
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

	// Error state
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
							Back
						</Button>
					</div>
				</div>
			</div>
		);
	}

	// No lesson state
	if (!lesson) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-zinc-500">
					<div className="max-w-3xl mx-auto p-6 bg-zinc-50 rounded-lg border border-zinc-200">
						<h2 className="text-xl font-semibold mb-4">No lesson available</h2>
						<p className="mb-4">This lesson could not be loaded.</p>
						<Button
							onClick={onBack}
							variant="outline"
							className="flex items-center gap-2"
						>
							<ArrowLeft className="w-4 h-4" />
							Back
						</Button>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
			<div className="max-w-4xl w-full mx-auto px-4 flex justify-center">
				<div
					className={cn(
						"w-full rounded-xl border shadow-sm flex flex-col my-8",
						isDarkMode
							? "bg-zinc-900 border-zinc-800"
							: "bg-white border-zinc-200",
					)}
				>
					{/* Header */}
					<div
						className={cn(
							"border-b p-6",
							isDarkMode
								? "border-zinc-800 bg-gradient-to-r from-emerald-900/20 to-teal-900/20"
								: "border-zinc-200 bg-gradient-to-r from-emerald-50 to-teal-50",
						)}
					>
						<div className="flex items-center justify-between mb-4">
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
								<ArrowLeft className="w-4 h-4" /> Back
							</button>

							<div className="flex items-center gap-2">
								{onRegenerate && (
									<Button
										onClick={() => onRegenerate(lesson.id)}
										variant="outline"
										size="sm"
										className="flex items-center gap-1"
									>
										<RotateCcw className="w-4 h-4" />
										Regenerate
									</Button>
								)}

								{onMarkComplete && (
									<Button
										onClick={() => onMarkComplete(lesson.id)}
										size="sm"
										className="flex items-center gap-1"
									>
										<CheckCircle className="w-4 h-4" />
										Complete
									</Button>
								)}
							</div>
						</div>

						<h1
							className={cn(
								"text-3xl font-bold",
								isDarkMode ? "text-white" : "text-zinc-900",
							)}
						>
							{lesson.title || lesson.slug || "Lesson"}
						</h1>
					</div>

					{/* Content */}
					<div
						className={cn(
							"p-6 md:p-8 prose prose-lg max-w-none",
							isDarkMode ? "prose-invert prose-emerald" : "prose-emerald",
						)}
					>
						<ContentRenderer content={lesson.md_source || lesson.content} />
					</div>
				</div>
			</div>
		</div>
	);
}
