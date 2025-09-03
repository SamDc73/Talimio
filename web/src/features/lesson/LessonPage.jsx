import { useState } from "react"
import { useParams } from "react-router-dom"
import RoadmapHeader from "@/components/header/RoadmapHeader"
import { CourseSidebar } from "@/components/sidebar"
import useAppStore, { selectSidebarOpen } from "@/stores/useAppStore"
import { LessonViewer } from "../course/components/LessonViewer"
import { useLessonPage } from "./hooks/useLessonPage"

/**
 * Lesson page component
 * Following state management guide: "Components are dumb" - all business logic in hooks
 * Uses combined useLessonPage hook for all data and actions
 */
export default function LessonPage() {
	const { lessonId } = useParams()
	const [mode, setMode] = useState("outline")
	const isOpen = useAppStore(selectSidebarOpen)

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
		handleBack,
		handleLessonClick,
		handleMarkComplete,
		handleRegenerate,
	} = useLessonPage(lessonId)

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-lg">Loading lesson...</div>
			</div>
		)
	}

	if (hasError) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-center">
					<h2 className="text-xl font-semibold mb-2 text-red-600">Error Loading Lesson</h2>
					<p className="text-gray-600 mb-4">{errorMessage}</p>
					<button
						type="button"
						onClick={handleBack}
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
						onClick={handleBack}
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
					modules={modules}
					onLessonClick={handleLessonClick}
					courseId={courseId}
					currentLessonId={lessonId}
				/>

				{/* Main lesson content */}
				<div className="flex flex-1 main-content transition-all duration-300 ease-in-out">
					<LessonViewer
						lesson={lesson}
						onBack={handleBack}
						isLoading={isLoading}
						error={error}
						onMarkComplete={handleMarkComplete}
						onRegenerate={handleRegenerate}
					/>
				</div>
			</div>
		</div>
	)
}
