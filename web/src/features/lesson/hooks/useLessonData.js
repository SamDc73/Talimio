import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { fetchLessonById, markLessonComplete, updateLessonProgress } from "../api/lessonApi"

/**
 * React Query hook for lesson data
 * Following state management guide: "TanStack Query for server data"
 *
 * @param {string} lessonId - The lesson ID to fetch
 * @returns {Object} - Object containing lesson data and loading state
 */
export function useLessonData(lessonId) {
	return useQuery({
		queryKey: ["lesson", lessonId],
		queryFn: () => fetchLessonById(lessonId),
		enabled: !!lessonId,
		staleTime: 5 * 60 * 1000, // Cache for 5 minutes
		refetchOnWindowFocus: false, // Avoid unnecessary refetch loops when window gains focus
		retry: (failureCount, error) => {
			// Don't retry on 404s or auth errors
			if (error?.status === 404 || error?.status === 401) {
				return false
			}
			return failureCount < 3
		},
	})
}

/**
 * Mutation hook for updating lesson progress
 * Following state management guide: mutations with optimistic updates
 */
export function useLessonProgressMutation() {
	const queryClient = useQueryClient()

	return useMutation({
		mutationFn: ({ lessonId, progressData }) => updateLessonProgress(lessonId, progressData),

		// Optimistic update
		onMutate: async ({ lessonId, progressData }) => {
			await queryClient.cancelQueries(["lesson", lessonId])
			const previous = queryClient.getQueryData(["lesson", lessonId])

			queryClient.setQueryData(["lesson", lessonId], (old) => ({
				...old,
				progress: progressData,
			}))

			return { previous, lessonId }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (context?.previous) {
				queryClient.setQueryData(["lesson", context.lessonId], context.previous)
			}
		},

		// Refetch after success
		onSettled: (_data, _error, { lessonId }) => {
			queryClient.invalidateQueries(["lesson", lessonId])
		},
	})
}

/**
 * Mutation hook for marking lesson as complete
 */
export function useLessonCompleteMutation() {
	const queryClient = useQueryClient()

	return useMutation({
		mutationFn: markLessonComplete,
		onSuccess: (_data, lessonId) => {
			// Update lesson cache to mark as complete
			queryClient.setQueryData(["lesson", lessonId], (old) => ({
				...old,
				completed: true,
				completedAt: new Date().toISOString(),
			}))

			// Invalidate related queries
			queryClient.invalidateQueries(["lesson", lessonId])
			queryClient.invalidateQueries(["courses"]) // Invalidate course progress
		},
	})
}
