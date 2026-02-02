import { useQuery } from "@tanstack/react-query"
import { useCourseService } from "@/api/courseApi"

/**
 * Simple hook to fetch course data
 * This hook provides basic course information without flow/graph functionality
 *
 * @param {string} courseId - The course ID to fetch
 * @returns {Object} - Object containing course data and loading state
 */
export function useCourseData(courseId) {
	const courseService = useCourseService(courseId)

	const {
		data: course,
		isLoading,
		error,
		refetch: initializeCourse,
	} = useQuery({
		queryKey: ["course", courseId],
		queryFn: async () => {
			if (!courseId) return null
			return await courseService.fetchCourse()
		},
		enabled: !!courseId,
		staleTime: 5 * 60 * 1000, // Cache for 5 minutes
	})

	return {
		course,
		isLoading,
		error,
		initializeCourse,
	}
}
