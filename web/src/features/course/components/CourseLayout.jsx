import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom"

import FullPageLoader from "@/components/FullPageLoader"
import { useCourseContext } from "@/features/course/CourseContext.jsx"
import { CourseHeader } from "@/features/course/components/CourseHeader"
import CourseSidebarContainer from "@/features/course/components/CourseSidebarContainer.jsx"
import { cn } from "@/lib/utils"
import useAppStore, { selectSidebarOpen, selectToggleSidebar } from "@/stores/useAppStore"

function getModeFromPath(pathname, courseId) {
	if (!courseId) {
		return "outline"
	}

	const base = `/course/${courseId}`

	if (pathname.startsWith(`${base}/track`)) {
		return "track"
	}

	if (pathname.startsWith(`${base}/documents`)) {
		return "documents"
	}

	// Lesson routes share the same header mode as outline
	return "outline"
}

/**
 * Layout component for course/lesson pages.
 * Provides persistent header and sidebar that don't unmount during navigation.
 */
export default function CourseLayout() {
	const isOpen = useAppStore(selectSidebarOpen)
	const toggleSidebar = useAppStore(selectToggleSidebar)
	const navigate = useNavigate()
	const { pathname } = useLocation()
	const { lessonId } = useParams()

	// Course context is only loaded when this layout is rendered
	const { courseId, courseName, modules, adaptiveEnabled, adaptiveProgressPct, isLoading } = useCourseContext()

	const mode = getModeFromPath(pathname, courseId)

	const handleModeChange = (nextMode) => {
		if (!courseId || nextMode === mode) {
			return
		}

		if (nextMode === "track") {
			navigate(`/course/${courseId}/track`)
			return
		}

		if (nextMode === "documents") {
			navigate(`/course/${courseId}/documents`)
			return
		}

		// Default to outline
		navigate(`/course/${courseId}`)
	}

	const handleLessonClick = (_moduleId, clickedLessonId) => {
		if (!courseId || !clickedLessonId) {
			return
		}
		navigate(`/course/${courseId}/lesson/${clickedLessonId}`)
	}

	const contentClasses = cn("flex flex-1 pt-16 pb-8 transition-all duration-300 ease-in-out", isOpen ? "ml-80" : "ml-0")

	if (isLoading) {
		return <FullPageLoader message="Loading your course..." />
	}

	if (!courseId) {
		return (
			<div className="flex h-screen items-center justify-center">
				<div className="text-center">
					<h2 className="mb-2 text-xl font-semibold">Course Not Found</h2>
					<p className="mb-4 text-muted-foreground">No course ID provided.</p>
				</div>
			</div>
		)
	}

	return (
		<div className="flex min-h-screen flex-col bg-background">
			<CourseHeader
				mode={mode}
				onModeChange={handleModeChange}
				courseId={courseId}
				courseName={courseName}
				adaptiveEnabled={adaptiveEnabled}
				progress={adaptiveProgressPct}
				isOpen={isOpen}
				toggleSidebar={toggleSidebar}
			/>
			<div className="flex h-screen">
				<CourseSidebarContainer
					modules={modules || []}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					activeLessonId={lessonId}
					adaptiveEnabled={adaptiveEnabled}
					adaptiveProgressPct={adaptiveProgressPct}
				/>
				<div className={contentClasses}>
					<Outlet />
				</div>
			</div>
		</div>
	)
}
