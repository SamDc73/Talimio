import { useNavigate } from "react-router-dom"

/**
 * Generate the canonical course URL with optional lesson segment.
 * @param {string} courseId - Course ID
 * @param {string} [lessonId] - Optional lesson ID
 * @param {Object} [query] - Optional search params
 * @returns {string} Course URL
 */
export function generateCourseUrl(courseId, lessonId = null, query = null) {
	if (!courseId) return "/"

	const queryParams = new URLSearchParams()
	if (query && typeof query === "object") {
		for (const [key, value] of Object.entries(query)) {
			if (value === undefined || value === null || value === false || value === "") {
				continue
			}
			queryParams.set(key, String(value))
		}
	}

	const querySuffix = queryParams.size > 0 ? `?${queryParams.toString()}` : ""

	if (lessonId) {
		return `/course/${courseId}/lesson/${lessonId}${querySuffix}`
	}

	return `/course/${courseId}${querySuffix}`
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

		goToLesson: (courseId, lessonId, query = null) => {
			if (!courseId || !lessonId) return
			navigate(generateCourseUrl(courseId, lessonId, query))
		},
	}
}
