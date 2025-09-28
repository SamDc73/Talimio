import CourseView from "@/features/course/CourseView"
import { useCourseContext } from "@/hooks/useCourseContext"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { useCourseNavigation } from "@/utils/navigationUtils"
import RoadmapHeader from "./header/RoadmapHeader"
import { CourseSidebar } from "./sidebar"

/**
 * Layout component for course/lesson pages.
 * Provides persistent header and sidebar that don't unmount during navigation.
 */
export default function CourseLayout() {
	const isOpen = useAppStore(selectSidebarOpen)
	const { goToLesson } = useCourseNavigation()

	// Course context is only loaded when this layout is rendered
	const { courseId, lessonId, mode, setMode, courseName, modules, isLoading } = useCourseContext()

	const handleLessonClick = (_moduleId, lessonId) => {
		// The sidebar passes (moduleId, lessonId) but we only need lessonId for navigation
		goToLesson(courseId, lessonId)
	}

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-lg">Loading...</div>
			</div>
		)
	}

	return (
		<div
			className={`roadmap-container ${isOpen ? "sidebar-open" : "sidebar-closed"}`}
			style={{ margin: 0, padding: 0 }}
		>
			<RoadmapHeader mode={mode} onModeChange={setMode} courseId={courseId} courseName={courseName} />
			<div className="flex h-screen">
				<CourseSidebar
					modules={modules || []}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					activeLessonId={lessonId}
				/>
				<div className="flex flex-1 main-content transition-all duration-300 ease-in-out">
					{/* Render CourseView directly with proper props */}
					<CourseView mode={mode} modules={modules} roadmapId={courseId} />
				</div>
			</div>
			{/* ChatSidebar is globally mounted in App.jsx */}
		</div>
	)
}
