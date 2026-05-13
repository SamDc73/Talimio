import { useQuery } from "@tanstack/react-query"
import { fetchCourseById } from "@/api/courseApi"

export function isDraftGeneratedCourse(course) {
	const modules = Array.isArray(course?.modules) ? course.modules : []
	return Boolean(course?.title?.startsWith("Generating:")) && modules.length === 0
}

/**
 * Simple hook to fetch course data
 * This hook provides basic course information without flow/graph functionality
 *
 * @param {string} courseId - The course ID to fetch
 * @returns {Object} - Object containing course data and loading state
 */
export function useCourseData(courseId) {
	const {
		data: course,
		isLoading,
		error,
		refetch: initializeCourse,
	} = useQuery({
		queryKey: ["course", courseId],
		queryFn: ({ signal }) => {
			if (!courseId) return null
			return fetchCourseById(courseId, signal)
		},
		enabled: !!courseId,
		refetchInterval: (query) => (isDraftGeneratedCourse(query.state.data) ? 2000 : false),
		staleTime: 5 * 60 * 1000, // Cache for 5 minutes
	})

	return {
		course,
		isLoading,
		error,
		initializeCourse,
	}
}
