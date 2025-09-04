import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { useCourseData } from "@/features/course/hooks/useCourseData"
import { useOutlineData } from "@/features/course/hooks/useOutlineData"
import { fetchLessonById } from "@/features/lesson/api/lessonApi"

/**
 * Hook to detect if we're in a course/lesson context and fetch necessary data.
 * This runs at App level to provide persistent header/sidebar.
 */
export function useCourseContext() {
	const location = useLocation()
	const [courseId, setCourseId] = useState(null)
	const [lessonId, setLessonId] = useState(null)
	const [mode, setMode] = useState("outline")
	const lastFetchedLessonIdRef = useRef(null)

	// Parse courseId and lessonId from URL
	useEffect(() => {
		const path = location.pathname

		// Check for course routes: /course/:courseId
		const courseMatch = path.match(/\/course\/([^/]+)/)
		if (courseMatch) {
			const courseIdFromUrl = courseMatch[1]
			setCourseId(courseIdFromUrl)
			setLessonId(null) // Course route has no lesson
			return
		}

		// Check for standalone lesson route: /lesson/:lessonId
		const lessonMatch = path.match(/^\/lesson\/([^/]+)/)
		if (lessonMatch) {
			const lessonIdFromUrl = lessonMatch[1]
			setLessonId(lessonIdFromUrl)

			// Only fetch if we haven't already fetched this lesson
			if (lastFetchedLessonIdRef.current !== lessonIdFromUrl) {
				lastFetchedLessonIdRef.current = lessonIdFromUrl
				fetchLessonById(lessonIdFromUrl)
					.then((lesson) => {
						const id = lesson?.roadmap_id || lesson?.course_id
						if (id) {
							setCourseId(id)
						}
					})
					.catch((_error) => {
						setCourseId(null)
						setLessonId(null)
					})
			}
			return
		}

		// Not in course context - clear everything
		setCourseId(null)
		setLessonId(null)
		lastFetchedLessonIdRef.current = null
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
