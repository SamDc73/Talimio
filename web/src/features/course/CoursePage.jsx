import { useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"

import { CourseHeader } from "@/components/header/CourseHeader"
import { CourseSidebar } from "@/components/sidebar"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen, selectToggleSidebar } from "@/stores/useAppStore"
import { useCourseNavigation } from "@/utils/navigationUtils"
import { useCourseService } from "./api/courseApi"
import { useCourseData } from "./hooks/useCourseData"
import { useOutlineData } from "./hooks/useOutlineData"
import DocumentsView from "./views/DocumentsView"
import LessonView from "./views/LessonView"
import OutlineView from "./views/OutlineView"
import TrackView from "./views/TrackView"

/**
 * Main container component for the Course feature
 * Handles switching between different views and lesson display
 */
function CoursePage({ courseId: propCourseId, ref: _ref }) {
	const { courseId: routeCourseId, lessonId } = useParams()
	const courseId = propCourseId ?? routeCourseId // Support both props and URL params

	const { isLoading: courseLoading, course } = useCourseData(courseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)
	const isOpen = useAppStore(selectSidebarOpen)
	const toggleSidebar = useAppStore(selectToggleSidebar)
	const [mode, setMode] = useState("outline") // Default to outline view
	const [lastAdaptiveProgressPct, setLastAdaptiveProgressPct] = useState(undefined)
	const { goToLesson } = useCourseNavigation()
	const isAdaptiveCourse = course?.adaptive_enabled === true || course?.adaptiveEnabled === true

	// Adaptive progress (avgMastery from concept frontier) → header progress
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

	// Preserve last known adaptive progress to avoid flicker to 0% between renders
	useEffect(() => {
		if (typeof adaptiveProgressPct === "number") {
			setLastAdaptiveProgressPct(adaptiveProgressPct)
		}
	}, [adaptiveProgressPct])

	useEffect(() => {
		// Prevent adaptive view from sticking on non-adaptive courses
		if (!isAdaptiveCourse && mode === "adaptive") {
			setMode("outline")
		}
	}, [isAdaptiveCourse, mode])

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	const isLoading = courseLoading || modulesLoading
	const courseName = course?.title || "Course"
	const moduleList = Array.isArray(modules) ? modules : []

	// Handle lesson click navigation
	const handleLessonClick = (_moduleId, clickedLessonId) => {
		goToLesson(courseId, clickedLessonId)
	}

	if (isLoading) {
		return (
			<div className="w-screen h-screen flex items-center justify-center">
				<div className="text-lg">Loading your course...</div>
			</div>
		)
	}

	if (!courseId) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-center">
					<h2 className="text-xl font-semibold mb-2">Course Not Found</h2>
					<p className="text-muted-foreground mb-4">No course ID provided.</p>
				</div>
			</div>
		)
	}

	return (
		<div className="flex min-h-screen flex-col bg-background">
			<CourseHeader
				mode={mode}
				onModeChange={setMode}
				courseId={courseId}
				courseName={courseName}
				adaptiveEnabled={isAdaptiveCourse}
				hasModules={moduleList.length > 0}
				progress={adaptiveProgressPct}
				isOpen={isOpen}
				toggleSidebar={toggleSidebar}
			/>

			<div className="flex h-screen">
				<CourseSidebar
					modules={moduleList}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					activeLessonId={lessonId}
					adaptiveEnabled={isAdaptiveCourse}
					adaptiveProgressPct={typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : lastAdaptiveProgressPct}
				/>

				<div className={contentClasses}>
					{lessonId ? (
						<LessonView courseId={courseId} lessonId={lessonId} />
					) : mode === "documents" ? (
						<DocumentsView courseId={courseId} />
					) : mode === "track" ? (
						<TrackView courseId={courseId} modules={moduleList} adaptiveEnabled={isAdaptiveCourse} />
					) : (
						<OutlineView courseId={courseId} modules={moduleList} adaptiveEnabled={isAdaptiveCourse} />
					)}
				</div>
			</div>
		</div>
	)
}

export default CoursePage
