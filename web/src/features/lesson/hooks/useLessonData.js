import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCourseProgress } from "@/features/course/hooks/useCourseProgress"
import { useUpdateProgress } from "@/hooks/useProgress"
import { fetchLesson } from "../api/lessonApi"

const toSnakeCase = (key) => key.replace(/([A-Z])/g, "_$1").toLowerCase()

const normalizeMetadataFields = (metadata = {}) => {
	const normalized = {}

	Object.entries(metadata).forEach(([key, value]) => {
		if (value === undefined) {
			return
		}

		const targetKey = key.includes("_") ? key : toSnakeCase(key)
		if (["completed_lessons", "current_lesson_id", "total_lessons", "content_type"].includes(targetKey)) {
			return
		}

		normalized[targetKey] = value
	})

	return normalized
}

/**
 * React Query hook for lesson data
 * Following state management guide: "TanStack Query for server data"
 *
 * @param {string} lessonId - The lesson ID to fetch
 * @returns {Object} - Object containing lesson data and loading state
 */
export function useLessonData(courseId, lessonId) {
	return useQuery({
		queryKey: ["lesson", courseId, lessonId],
		queryFn: () => fetchLesson(courseId, lessonId),
		enabled: Boolean(courseId && lessonId),
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
export function useLessonProgressMutation(courseId) {
	const queryClient = useQueryClient()
	const updateProgress = useUpdateProgress()
	const { toggleCompletion } = useCourseProgress(courseId)

	return useMutation({
		mutationFn: async ({ lessonId, progress }) => {
			if (!courseId) {
				throw new Error("Course ID is required to update lesson progress")
			}

			if (!lessonId) {
				throw new Error("Lesson ID is required to update lesson progress")
			}

			if (progress?.lessonCompleted !== undefined) {
				return toggleCompletion(lessonId)
			}

			const metadataInput = progress?.metadata || {}
			const completedLessonsSource =
				progress?.completed_lessons ??
				progress?.completedLessons ??
				metadataInput.completed_lessons ??
				metadataInput.completedLessons ??
				[]

			const completedLessons = completedLessonsSource.map((lesson) => String(lesson))

			const totalLessons =
				progress?.total_lessons ??
				progress?.totalLessons ??
				metadataInput.total_lessons ??
				metadataInput.totalLessons ??
				(completedLessons.length || 0)

			const currentLessonId =
				progress?.current_lesson_id ??
				progress?.currentLessonId ??
				metadataInput.current_lesson_id ??
				metadataInput.currentLessonId ??
				lessonId

			const progressPercentage =
				progress?.progress_percentage ??
				progress?.percentage ??
				(totalLessons > 0 ? Math.round((completedLessons.length / totalLessons) * 100) : 0)

			const additionalMetadata = normalizeMetadataFields(metadataInput)

			return updateProgress.mutateAsync({
				contentId: courseId,
				progress: progressPercentage,
				metadata: {
					content_type: "course",
					completed_lessons: completedLessons,
					current_lesson_id: String(currentLessonId),
					total_lessons: totalLessons,
					...additionalMetadata,
				},
			})
		},

		// Optimistic update
		onMutate: async ({ lessonId, progress }) => {
			if (!courseId || !lessonId) {
				return {}
			}

			await queryClient.cancelQueries(["lesson", courseId, lessonId])
			const previous = queryClient.getQueryData(["lesson", courseId, lessonId])

			queryClient.setQueryData(["lesson", courseId, lessonId], (old) => ({
				...old,
				progress,
			}))

			return { previous, lessonId }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (!courseId || !context?.previous || !context.lessonId) {
				return
			}

			queryClient.setQueryData(["lesson", courseId, context.lessonId], context.previous)
		},

		// Refetch after success
		onSettled: (_data, _error, variables) => {
			if (!courseId || !variables?.lessonId) {
				return
			}

			queryClient.invalidateQueries(["lesson", courseId, variables.lessonId])
		},
	})
}

/**
 * Mutation hook for marking lesson as complete
 */
export function useLessonCompleteMutation(courseId) {
	const queryClient = useQueryClient()
	const { toggleCompletion } = useCourseProgress(courseId)

	return useMutation({
		mutationFn: async ({ lessonId }) => {
			if (!courseId) {
				throw new Error("Course ID is required to mark a lesson complete")
			}

			if (!lessonId) {
				throw new Error("Lesson ID is required to mark a lesson complete")
			}

			await toggleCompletion(lessonId)
		},
		onSuccess: (_data, variables) => {
			if (!courseId || !variables?.lessonId) {
				return
			}

			const lessonId = variables.lessonId

			// Update lesson cache to mark as complete
			queryClient.setQueryData(["lesson", courseId, lessonId], (old) => ({
				...old,
				completed: true,
				completedAt: new Date().toISOString(),
			}))

			// Invalidate related queries
			queryClient.invalidateQueries(["lesson", courseId, lessonId])
			queryClient.invalidateQueries(["courses"]) // Invalidate course progress
		},
	})
}
