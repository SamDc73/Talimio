import { useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { CourseHeader } from "@/components/header/CourseHeader"
import { CourseSidebar } from "@/components/sidebar"
import { useCourseService } from "@/features/course/api/courseApi"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { LessonViewer } from "../course/components/LessonViewer"
import { useLessonPage } from "./hooks/useLessonPage"

/**
 * Lesson page component
 * Following state management guide: "Components are dumb" - all business logic in hooks
 * Uses combined useLessonPage hook for all data and actions
 */
export default function LessonPage() {
	const { courseId: routeCourseId, lessonId } = useParams()
	const [mode, setMode] = useState("outline")
	const [lastAdaptiveProgressPct, setLastAdaptiveProgressPct] = useState(undefined)
	const isOpen = useAppStore(selectSidebarOpen)

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	// Combined hook provides all data and actions
	// Following state management guide: "Combine stores via custom hooks"
	const {
		lesson,
		courseId,
		modules,
		isLoading,
		error,
		hasError,
		errorMessage,
		courseName,
		isAdaptiveCourse,
		handleBack,
		handleLessonClick,
		handleMarkComplete,
		handleRegenerate,
	} = useLessonPage(routeCourseId, lessonId)

	// Adaptive progress (avgMastery) for header/sidebar consistency
	const courseService = useCourseService(courseId)
	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId) && isAdaptiveCourse,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})
	const adaptiveProgressPct =
		typeof frontierData?.avgMastery === "number" ? Math.round(frontierData.avgMastery * 100) : undefined
	useEffect(() => {
		if (typeof adaptiveProgressPct === "number") {
			setLastAdaptiveProgressPct(adaptiveProgressPct)
		}
	}, [adaptiveProgressPct])

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-lg">Loading lesson...</div>
			</div>
		)
	}

	if (hasError) {
		return (
			<div className="flex h-screen items-center justify-center">
				<div className="text-center">
					<h2 className="mb-2 text-xl font-semibold text-destructive">Error Loading Lesson</h2>
					<p className="mb-4 text-muted-foreground">{errorMessage}</p>
					<button
						type="button"
						onClick={handleBack}
						className="rounded bg-primary px-4 py-2 text-primary-foreground transition-colors hover:bg-primary/90"
					>
						Go Back
					</button>
				</div>
			</div>
		)
	}

	if (!lesson) {
		return (
			<div className="flex h-screen items-center justify-center">
				<div className="text-center">
					<h2 className="mb-2 text-xl font-semibold">Lesson Not Found</h2>
					<p className="mb-4 text-muted-foreground">The lesson you're looking for could not be found.</p>
					<button
						type="button"
						onClick={handleBack}
						className="rounded bg-primary px-4 py-2 text-primary-foreground transition-colors hover:bg-primary/90"
					>
						Go Back
					</button>
				</div>
			</div>
		)
	}

	// Render lesson page with same structure as CoursePage
	return (
		<div className="flex min-h-screen flex-col bg-background">
			<CourseHeader
				mode={mode}
				onModeChange={setMode}
				courseId={courseId}
				courseName={courseName}
				adaptiveEnabled={isAdaptiveCourse}
				progress={typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : lastAdaptiveProgressPct}
			/>

			<div className="flex h-screen">
				{/* Always show sidebar with modules data - same as CoursePage */}
				<CourseSidebar
					modules={modules}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					activeLessonId={lessonId}
					adaptiveEnabled={isAdaptiveCourse}
					adaptiveProgressPct={typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : lastAdaptiveProgressPct}
				/>

				{/* Main lesson content */}
				<div className={contentClasses}>
					<LessonViewer
						lesson={lesson}
						onBack={handleBack}
						isLoading={isLoading}
						error={error}
						onMarkComplete={handleMarkComplete}
						onRegenerate={handleRegenerate}
						courseId={courseId}
						modules={modules}
						onLessonNavigate={handleLessonClick}
						adaptiveEnabled={isAdaptiveCourse}
					/>
				</div>
			</div>
		</div>
	)
}
