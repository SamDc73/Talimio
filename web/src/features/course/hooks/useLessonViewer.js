import { useState } from "react"
import { fetchLesson } from "../api/lessonsApi"

/**
 *  lesson viewer hook
 */
export function useLessonViewer(courseId) {
	const [lesson, setLesson] = useState(null)
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)

	/**
	 * Load a lesson by ID, generate if needed
	 */
	const loadLesson = useCallback(
		async (lessonId) => {
			if (!courseId || !lessonId) {
				setError("Missing required IDs")
				return
			}

			setIsLoading(true)
			setError(null)

			try {
				const lessonData = await fetchLesson(courseId, lessonId)

				// Check if content is actually available
				if (!lessonData?.md_source && !lessonData?.content) {
					setError(
						"Lesson content is not available. The system is attempting to generate it. Please try again in a moment."
					)
					console.log("Content Generation in Progress")
				} else {
					setLesson(lessonData)
				}
			} catch (err) {
				// Provide more specific error messages based on status
				let errorMessage = err.message || "Failed to load lesson"

				if (err.message?.includes("503") || err.message?.includes("Service Unavailable")) {
					errorMessage = "The lesson generation service is temporarily unavailable. Please try again in a few moments."
				} else if (err.message?.includes("500")) {
					errorMessage = "An unexpected error occurred while loading the lesson. Please try refreshing the page."
				} else if (err.message?.includes("404")) {
					errorMessage = "Lesson not found. Please check if the lesson exists."
				}

				setError(errorMessage)
				console.log("Error Loading Lesson")
			} finally {
				setIsLoading(false)
			}
		},
		[courseId]
	)

	/**
	 * Generate a new lesson (requires moduleId, so disabled for now)
	 */
	const createLesson = useCallback(async () => {
		console.log("Feature not available")
	}, [])

	/**
	 * Clear the current lesson
	 */
	const clearLesson = useCallback(() => {
		setLesson(null)
		setError(null)
	}, [])

	return {
		lesson,
		isLoading,
		error,
		loadLesson,
		createLesson,
		clearLesson,
	}
}
