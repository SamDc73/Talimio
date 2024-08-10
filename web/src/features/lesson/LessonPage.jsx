import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import RoadmapHeader from "@/components/header/RoadmapHeader"
import { CourseSidebar } from "@/components/sidebar"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { useCourseNavigation } from "../../utils/navigationUtils"
import { fetchLessonById } from "../course/api/lessonsApi"
import { LessonViewer } from "../course/components/LessonViewer"
import { useOutlineData } from "../course/hooks/useOutlineData"
import { useRoadmapState } from "../course/hooks/useRoadmapState"

/**
 * Standalone lesson page that loads a lesson by ID
 * Fetches course data separately to provide consistent header and sidebar experience
 * Uses the same data fetching pattern as CoursePage for consistency
 */
export default function LessonPage() {
	const { lessonId } = useParams()
	const navigate = useNavigate()
	const [lesson, setLesson] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const [mode, setMode] = useState("outline")
	const isOpen = useAppStore(selectSidebarOpen)
	const { goToLesson } = useCourseNavigation()

	// Get course ID from lesson data
	const courseId = lesson?.roadmap_id || lesson?.course_id

	// Fetch course data and modules using the same hooks as CoursePage
	const { isLoading: roadmapLoading, roadmap } = useRoadmapState(
		courseId,
		() => {} // No error handler needed for now
	)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)

	// Calculate loading states
	const isDataLoading = loading || roadmapLoading || modulesLoading
	const courseName = roadmap?.title || "Course"

	useEffect(() => {
		if (!lessonId) return

		const fetchLessonData = async () => {
			setLoading(true)
			setError(null)

			try {
				// Fetch lesson by ID only (no courseId needed)
				const lessonData = await fetchLessonById(lessonId)
				setLesson(lessonData)
			} catch (err) {
				setError(err.message || "Failed to load lesson")
			} finally {
				setLoading(false)
			}
		}

		fetchLessonData()
	}, [lessonId])

	const handleBack = () => {
		if (courseId) {
			// Navigate to the course page if we have a course ID
			navigate(`/course/${courseId}`)
		} else {
			// Otherwise go back in history
			window.history.back()
		}
	}

	const handleLessonClick = (clickedLessonId) => {
		// Use the same navigation logic as CoursePage
		if (courseId) {
			goToLesson(courseId, clickedLessonId)
		} else {
			// Fallback to direct lesson navigation
			navigate(`/lesson/${clickedLessonId}`)
		}
	}

	if (isDataLoading) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-lg">Loading lesson...</div>
			</div>
		)
	}

	if (error) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-center">
					<h2 className="text-xl font-semibold mb-2 text-red-600">Error Loading Lesson</h2>
					<p className="text-gray-600 mb-4">{error}</p>
					<button
						type="button"
						onClick={() => window.history.back()}
						className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
					>
						Go Back
					</button>
				</div>
			</div>
		)
	}

	if (!lesson) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-center">
					<h2 className="text-xl font-semibold mb-2">Lesson Not Found</h2>
					<p className="text-gray-600 mb-4">The lesson you're looking for could not be found.</p>
					<button
						type="button"
						onClick={() => window.history.back()}
						className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
					>
						Go Back
					</button>
				</div>
			</div>
		)
	}

	// Render lesson page with same structure as CoursePage
	return (
		<div
			className={`roadmap-container ${isOpen ? "sidebar-open" : "sidebar-closed"}`}
			style={{ margin: 0, padding: 0 }}
		>
			<RoadmapHeader mode={mode} onModeChange={setMode} courseId={courseId} courseName={courseName} />

			<div className="flex h-screen">
				{/* Always show sidebar with modules data - same as CoursePage */}
				<CourseSidebar
					modules={modules || []}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					currentLessonId={lessonId}
				/>

				{/* Main lesson content */}
				<div className="flex flex-1 main-content transition-all duration-300 ease-in-out">
					<LessonViewer lesson={lesson} onBack={handleBack} isLoading={loading} error={error} />
				</div>
			</div>
		</div>
	)
}
