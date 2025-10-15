import { useEffect, useState } from "react"
import { useLocation } from "react-router-dom"
import { useCourseData } from "./useCourseData"
import { useOutlineData } from "./useOutlineData"

/**
 * Hook to detect if we're in a course/lesson context and fetch necessary data.
 * This runs at App level to provide persistent header/sidebar.
 */
export function useCourseContext() {
	const location = useLocation()
	const [courseId, setCourseId] = useState(null)
	const [lessonId, setLessonId] = useState(null)
	const [mode, setMode] = useState("outline")

	// Parse courseId and lessonId from URL
	useEffect(() => {
		const path = location.pathname

		const courseMatch = path.match(/^\/course\/([^/]+)(?:\/lesson\/([^/]+))?$/)
		if (courseMatch) {
			setCourseId(courseMatch[1])
			setLessonId(courseMatch[2] ?? null)
			return
		}

		// Not in course context - clear everything
		setCourseId(null)
		setLessonId(null)
		setMode("outline")
	}, [location.pathname])

	// Determine if we should show course layout
	const showCourseLayout = courseId !== null

	// Fetch course data - hooks handle null courseId internally
	const { isLoading: roadmapLoading, roadmap } = useCourseData(courseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)

	const isLoading = courseId && (roadmapLoading || modulesLoading)
	const courseName = roadmap?.title || "Course"

	return {
		showCourseLayout,
		courseId,
		lessonId,
		mode,
		setMode,
		courseName,
		modules,
		roadmap,
		isLoading,
	}
}
