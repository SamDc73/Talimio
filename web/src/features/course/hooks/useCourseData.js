import { useQuery } from "@tanstack/react-query"
import { useCourseService } from "../api/courseApi"

/**
 * Simple hook to fetch course data (replaces useRoadmapState)
 * This hook provides basic course information without flow/graph functionality
 *
 * @param {string} courseId - The course ID to fetch
 * @returns {Object} - Object containing roadmap data and loading state
 */
export function useCourseData(courseId) {
	const courseService = useCourseService(courseId)

	const {
		data: roadmap,
		isLoading,
		error,
		refetch: initializeRoadmap,
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
		roadmap,
		isLoading,
		error,
		initializeRoadmap,
	}
}
