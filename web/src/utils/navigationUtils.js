import { useNavigate } from "react-router-dom"

/**
 * Generate the canonical course URL with optional lesson segment.
 * @param {string} courseId - Course ID
 * @param {string} [lessonId] - Optional lesson ID
 * @returns {string} Course URL
 */
export function generateCourseUrl(courseId, lessonId = null) {
	if (!courseId) return "/"

	if (lessonId) {
		return `/course/${courseId}/lesson/${lessonId}`
	}

	return `/course/${courseId}`
}

/**
 * Hook for course-aware navigation
 */
export function useCourseNavigation() {
	const navigate = useNavigate()

	return {
		goToCourse: (courseId) => {
			if (!courseId) return
			navigate(generateCourseUrl(courseId))
		},

		goToLesson: (courseId, lessonId) => {
			if (!courseId || !lessonId) return
			navigate(generateCourseUrl(courseId, lessonId))
		},
	}
}
