import { useEffect, useState } from "react"
import { useLocation } from "react-router-dom"
import { fetchLessonById } from "@/features/course/api/lessonsApi"
import { useOutlineData } from "@/features/course/hooks/useOutlineData"
import { useRoadmapState } from "@/features/course/hooks/useRoadmapState"

/**
 * Hook to detect if we're in a course/lesson context and fetch necessary data.
 * This runs at App level to provide persistent header/sidebar.
 */
export function useCourseContext() {
	const location = useLocation()
	const [courseId, setCourseId] = useState(null)
	const [lessonId, setLessonId] = useState(null)
	const [mode, setMode] = useState("outline")
	const [fetchingLesson, setFetchingLesson] = useState(null) // Track which lesson we're fetching

	// Parse courseId and lessonId from URL
	useEffect(() => {
		const path = location.pathname

		// Check for course routes: /course/:courseId or /course/:courseId/lesson/:lessonId
		const courseMatch = path.match(/\/course\/([^/]+)/)
		if (courseMatch) {
			setCourseId(courseMatch[1])
			const lessonMatch = path.match(/\/lesson\/([^/]+)/)
			setLessonId(lessonMatch ? lessonMatch[1] : null)
			setFetchingLesson(null) // Clear any pending fetches
			return
		}

		// Check for standalone lesson route: /lesson/:lessonId
		const lessonMatch = path.match(/^\/lesson\/([^/]+)/)
		if (lessonMatch) {
			const lessonIdFromUrl = lessonMatch[1]
			setLessonId(lessonIdFromUrl)

			// Only fetch if we're not already fetching this lesson
			if (fetchingLesson !== lessonIdFromUrl) {
				setFetchingLesson(lessonIdFromUrl)
				fetchLessonById(lessonIdFromUrl)
					.then((lesson) => {
						const id = lesson?.roadmap_id || lesson?.course_id
						if (id) {
							setCourseId(id)
						}
						setFetchingLesson(null)
					})
					.catch(() => {
						// Failed to fetch, clear context
						setCourseId(null)
						setLessonId(null)
						setFetchingLesson(null)
					})
			}
			return
		}

		// Not in course context - clear everything immediately
		setCourseId(null)
		setLessonId(null)
		setFetchingLesson(null)
		setMode("outline") // Reset mode too
	}, [location.pathname, fetchingLesson])

	// Determine if we should show course layout
	const showCourseLayout = courseId !== null

	// Fetch course data - hooks handle null courseId internally
	const { isLoading: roadmapLoading, roadmap } = useRoadmapState(
		courseId,
		() => {} // No error handler needed
	)
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
