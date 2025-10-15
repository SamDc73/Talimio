import { useState } from "react"
import { useParams } from "react-router-dom"

import RoadmapHeader from "@/components/header/RoadmapHeader"
import { CourseSidebar } from "@/components/sidebar"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { useCourseNavigation } from "../../utils/navigationUtils"
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
function CoursePage({ roadmapId: propRoadmapId, ref: _ref }) {
	const { courseId, lessonId } = useParams()
	const roadmapId = propRoadmapId || courseId // Support both props and URL params

	const { isLoading: roadmapLoading, roadmap } = useCourseData(roadmapId)
	const { modules, isLoading: modulesLoading } = useOutlineData(roadmapId)
	const isOpen = useAppStore(selectSidebarOpen)
	const [mode, setMode] = useState("outline") // Default to outline view
	const { goToLesson } = useCourseNavigation()

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	const isLoading = roadmapLoading || modulesLoading
	const courseName = roadmap?.title || "Course"

	// Handle lesson click navigation
	const handleLessonClick = (clickedLessonId) => {
		goToLesson(roadmapId, clickedLessonId)
	}

	if (isLoading) {
		return (
			<div className="w-screen h-screen flex items-center justify-center">
				<div className="text-lg">Loading your course...</div>
			</div>
		)
	}

	if (!roadmapId) {
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
			<RoadmapHeader mode={mode} onModeChange={setMode} courseId={roadmapId} courseName={courseName} />

			<div className="flex h-screen">
				<CourseSidebar modules={modules || []} onLessonClick={handleLessonClick} courseId={roadmapId} />

				{/* If viewing a lesson, show lesson view with same layout */}
				{lessonId ? (
					<div className={contentClasses}>
						<LessonView courseId={roadmapId} lessonId={lessonId} />
					</div>
				) : /* Course overview views */
				mode === "outline" ? (
					<div className={contentClasses}>
						<OutlineView roadmapId={roadmapId} modules={modules} />
					</div>
				) : mode === "track" ? (
					<div className={contentClasses}>
						<TrackView roadmapId={roadmapId} modules={modules} />
					</div>
				) : mode === "documents" ? (
					<div className={contentClasses}>
						<DocumentsView courseId={roadmapId} />
					</div>
				) : null}
			</div>
		</div>
	)
}

export default CoursePage
