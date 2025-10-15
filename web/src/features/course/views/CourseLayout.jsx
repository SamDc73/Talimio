import { forwardRef, useState } from "react"
import { useParams } from "react-router-dom"

import RoadmapHeader from "@/components/header/RoadmapHeader"
import { CourseSidebar } from "@/components/sidebar"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { useCourseNavigation } from "../../../utils/navigationUtils"
import { useCourseData } from "../hooks/useCourseData"
import { useOutlineData } from "../hooks/useOutlineData"
import DocumentsView from "./DocumentsView"
import LessonView from "./LessonView"
// import MapView from "./map";  // Temporarily hidden
import OutlineView from "./outline"
import TrackView from "./track"

const _BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

/**
 * Main container component for the Roadmap feature
 * Handles switching between map and outline views
 */
const RoadmapFlow = forwardRef(({ roadmapId, onError }, _ref) => {
	const { lessonId } = useParams() // Check if we're viewing a lesson
	const { isLoading: roadmapLoading, roadmap } = useCourseData(roadmapId)
	const { modules, isLoading: modulesLoading } = useOutlineData(roadmapId)
	const isOpen = useAppStore(selectSidebarOpen)
	const [mode, setMode] = useState("outline") // Default to outline view
	const { goToLesson } = useCourseNavigation()

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	const isLoading = roadmapLoading || modulesLoading
	const courseName = roadmap?.title || "Learn FastAPI"

	// Handle lesson click navigation
	const handleLessonClick = (clickedLessonId) => {
		goToLesson(roadmapId, clickedLessonId)
	}

	// No longer need module data for simplified routing

	if (isLoading) {
		return (
			<div className="w-screen h-screen flex items-center justify-center">
				<div className="text-lg">Loading your roadmap...</div>
			</div>
		)
	}

	if (!roadmapId) {
		return null
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
				) : // Map view temporarily hidden
				null}
			</div>
		</div>
	)
})

RoadmapFlow.displayName = "RoadmapFlow"

export default RoadmapFlow
