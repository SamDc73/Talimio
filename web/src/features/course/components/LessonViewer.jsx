import { ArrowLeft, ArrowRight, CheckCircle, RotateCcw } from "lucide-react"
import { useMemo, useRef } from "react"
import { Button } from "@/components/Button"
import { AdaptiveReviewPanel } from "./AdaptiveReviewPanel"
import { ContentRenderer } from "./ContentRenderer"

/**
 * LessonViewer - Presents a lesson with MDX content and actions
 * - Uses design tokens (bg-card, border-border, text-foreground, etc.)
 * - Dark mode via Tailwind's .dark class (no isDarkMode prop)
 * - Aligns with Tailwind v4 and Styling guides
 */
export function LessonViewer({
	lesson,
	isLoading,
	error,
	onBack,
	onMarkComplete,
	onRegenerate,
	modules = [],
	onLessonNavigate,
	adaptiveEnabled = false,
	courseId,
}) {
	const containerRef = useRef(null)

	// Calculate previous and next lessons from modules
	const { previousLesson, nextLesson } = useMemo(() => {
		if (!lesson?.id || !modules?.length) {
			return { previousLesson: null, nextLesson: null }
		}

		// Flatten all lessons from all modules
		const allLessons = []
		for (const module of modules) {
			if (Array.isArray(module?.lessons)) {
				for (const lessonItem of module.lessons) {
					allLessons.push(lessonItem)
				}
			}
		}

		// Find current lesson index
		const currentIndex = allLessons.findIndex((l) => String(l?.id) === String(lesson.id))
		if (currentIndex === -1) {
			return { previousLesson: null, nextLesson: null }
		}

		return {
			previousLesson: currentIndex > 0 ? allLessons[currentIndex - 1] : null,
			nextLesson: currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null,
		}
	}, [lesson?.id, modules])

	// Loading state
	if (isLoading) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-muted-foreground">
					<div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary mb-4" />
					<p>Loading lesson...</p>
				</div>
			</div>
		)
	}

	// Error state
	if (error) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-destructive">
					<div className="max-w-3xl mx-auto p-6 bg-destructive/10 rounded-lg border border-destructive/30">
						<h2 className="text-xl font-semibold mb-4">Error loading lesson</h2>
						<p className="mb-4">{error}</p>
						<Button onClick={onBack} variant="outline" size="sm">
							<ArrowLeft className="w-4 h-4" />
							Back
						</Button>
					</div>
				</div>
			</div>
		)
	}

	// No lesson state
	if (!lesson) {
		return (
			<div className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
				<div className="flex flex-col items-center justify-center min-h-full text-muted-foreground">
					<div className="max-w-3xl mx-auto p-6 bg-muted rounded-lg border border-border">
						<h2 className="text-xl font-semibold mb-4 text-foreground">No lesson available</h2>
						<p className="mb-4">This lesson could not be loaded.</p>
						<Button onClick={onBack} variant="outline" size="sm">
							<ArrowLeft className="w-4 h-4" />
							Back
						</Button>
					</div>
				</div>
			</div>
		)
	}

	return (
		<div ref={containerRef} className="h-[calc(100vh-4rem)] overflow-y-auto w-full">
			<div className="max-w-4xl w-full mx-auto px-4 flex justify-center">
				<div className="w-full rounded-lg border border-border bg-card shadow-sm flex flex-col my-8">
					{/* Header */}
						<div className="border-b border-border bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 p-6">
						<div className="flex items-center justify-between mb-5">
							<Button onClick={onBack} variant="secondary" size="sm">
								<ArrowLeft className="w-4 h-4" />
								Back
							</Button>

							<div className="flex items-center gap-2">
								{onRegenerate && (
									<Button onClick={() => onRegenerate(lesson.id)} variant="outline" size="sm">
										<RotateCcw className="w-4 h-4" />
										Regenerate
									</Button>
								)}

								{onMarkComplete && (
									<Button onClick={() => onMarkComplete(lesson.id)} size="sm">
										<CheckCircle className="w-4 h-4" />
										Complete
									</Button>
								)}
							</div>
						</div>

						<h1 className="text-3xl font-bold leading-tight text-foreground px-6">
							{lesson.title || lesson.slug || "Lesson"}
						</h1>
					</div>

					{/* Content */}
					<div className="p-6 md:p-8" data-selection-zone="true">
						<ContentRenderer
							content={lesson.md_source || lesson.content}
							lessonId={lesson.id}
							courseId={lesson.course_id}
						/>
					</div>

					{/* Adaptive Review Panel - blends seamlessly into lesson flow */}
					{adaptiveEnabled && courseId && lesson?.id && (
						<div className="px-6 md:px-8 pt-4">
							<AdaptiveReviewPanel
								courseId={courseId}
								lessonId={lesson.id}
								lessonConceptId={lesson.concept_id}
								adaptiveEnabled={adaptiveEnabled}
							/>
						</div>
					)}

					{/* Lesson Navigation - subtle footer navigation */}
					{onLessonNavigate && (previousLesson || nextLesson) && (
						<div className="px-6 md:px-8 pb-8 pt-4">
							<div className="flex items-center justify-between gap-4 pt-6 mt-6 border-t border-border/40">
								{previousLesson ? (
									<Button type="button" variant="outline" size="sm" onClick={() => onLessonNavigate(previousLesson.id)}>
										<ArrowLeft className="w-4 h-4" />
										Previous
									</Button>
								) : (
									<div />
								)}

								{nextLesson ? (
									<Button type="button" variant="default" size="sm" onClick={() => onLessonNavigate(nextLesson.id)} className="ml-auto">
										Next Lesson
										<ArrowRight className="w-4 h-4" />
									</Button>
								) : (
									<div />
								)}
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	)
}
