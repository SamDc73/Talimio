import { useState } from "react"
import { useParams } from "react-router-dom"

import { CourseHeader } from "@/components/header/CourseHeader"
import { CourseSidebar } from "@/components/sidebar"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen, selectToggleSidebar } from "@/stores/useAppStore"
import { useCourseNavigation } from "@/utils/navigationUtils"
import { useCourseData } from "./hooks/useCourseData"
import { useOutlineData } from "./hooks/useOutlineData"
import DocumentsView from "./views/DocumentsView"
import LessonView from "./views/LessonView"
import OutlineView from "./views/outline"
import TrackView from "./views/track"

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
	const { goToLesson } = useCourseNavigation()

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	const isLoading = courseLoading || modulesLoading
	const courseName = course?.title || "Course"

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
				isOpen={isOpen}
				toggleSidebar={toggleSidebar}
			/>

			<div className="flex h-screen">
				<CourseSidebar modules={modules || []} onLessonClick={handleLessonClick} courseId={courseId} />

				{/* If viewing a lesson, show lesson view with same layout */}
				{lessonId ? (
					<div className={contentClasses}>
						<LessonView courseId={courseId} lessonId={lessonId} />
					</div>
				) : mode === "outline" ? (
					<div className={contentClasses}>
						<OutlineView courseId={courseId} modules={modules} />
					</div>
				) : mode === "track" ? (
					<div className={contentClasses}>
						<TrackView courseId={courseId} modules={modules} />
					</div>
				) : mode === "documents" ? (
					<div className={contentClasses}>
						<DocumentsView courseId={courseId} />
					</div>
				) : null}
			</div>
		</div>
	)
}

export default CoursePage
