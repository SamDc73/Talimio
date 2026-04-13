import { useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useCourseNavigation } from "@/utils/navigationUtils"
import {
	useLessonCompleteMutation,
	useLessonNextPassMutation,
	useLessonProgressMutation,
	useLessonRegenerateMutation,
} from "./use-lesson-data"

/**
 * Business logic actions for lessons
 * Following state management guide: "Model actions as events - business logic in hooks, not components"
 */
export function useLessonActions(courseId) {
	const navigate = useNavigate()
	const { goToLesson } = useCourseNavigation()
	const progressMutation = useLessonProgressMutation(courseId)
	const completeMutation = useLessonCompleteMutation(courseId)
	const regenerateMutation = useLessonRegenerateMutation(courseId)
	const nextPassMutation = useLessonNextPassMutation(courseId)

	// Action: Navigate back from lesson
	const handleBack = useCallback(() => {
		if (courseId) {
			// Navigate to the course page if we have a course ID
			navigate(`/course/${courseId}`)
			return
		}

		// Otherwise go back in history
		window.history.back()
	}, [courseId, navigate])

	// Action: Navigate to another lesson
	const handleLessonNavigation = useCallback(
		(lessonId, targetCourseId) => {
			const courseToUse = targetCourseId ?? courseId
			if (!courseToUse || !lessonId) {
				return
			}
			goToLesson(courseToUse, lessonId)
		},
		[courseId, goToLesson]
	)

	// Action: Mark lesson as complete
	const handleMarkComplete = useCallback(
		(lessonId, targetCourseId) => {
			const courseToUse = targetCourseId ?? courseId
			if (!courseToUse || !lessonId) {
				return
			}

			completeMutation.mutate({ lessonId })

			// Emit event for cross-component communication
			// Following state management guide: "Event-Driven Updates"
			window.dispatchEvent(
				new CustomEvent("lessonComplete", {
					detail: { courseId: courseToUse, lessonId, timestamp: new Date().toISOString() },
				})
			)
		},
		[completeMutation, courseId]
	)

	// Action: Update lesson progress
	const handleProgressUpdate = useCallback(
		(lessonId, progress, targetCourseId) => {
			const courseToUse = targetCourseId ?? courseId
			if (!courseToUse || !lessonId) {
				return
			}

			progressMutation.mutate({ lessonId, progress })

			// Emit event for progress updates
			window.dispatchEvent(
				new CustomEvent("lessonProgressUpdate", {
					detail: { courseId: courseToUse, lessonId, progress },
				})
			)
		},
		[courseId, progressMutation]
	)

	// Action: Regenerate lesson content
	const handleRegenerate = useCallback(
		async (lessonId, critiqueText, applyAcrossCourse = false) => {
			if (!courseId || !lessonId) {
				return
			}

			const regeneratedLesson = await regenerateMutation.mutateAsync({
				lessonId,
				critiqueText,
				applyAcrossCourse,
			})

			window.dispatchEvent(
				new CustomEvent("lessonRegenerate", {
					detail: { courseId, lessonId, timestamp: new Date().toISOString() },
				})
			)

			return regeneratedLesson
		},
		[courseId, regenerateMutation]
	)

	const handleStartNextPass = useCallback(
		async (lessonId, { force = false } = {}) => {
			if (!courseId || !lessonId) {
				return
			}

			const nextPassLesson = await nextPassMutation.mutateAsync({
				lessonId,
				force,
			})

			window.dispatchEvent(
				new CustomEvent("lessonNextPass", {
					detail: { courseId, lessonId, force, timestamp: new Date().toISOString() },
				})
			)

			return nextPassLesson
		},
		[courseId, nextPassMutation]
	)

	return {
		// Navigation actions
		handleBack,
		handleLessonNavigation,

		// Progress actions
		handleMarkComplete,
		handleProgressUpdate,

		// Content actions
		handleRegenerate,
		handleStartNextPass,

		// Mutation states for UI feedback
		isCompletingLesson: completeMutation.isPending,
		isStartingNextPass: nextPassMutation.isPending,
		isRegeneratingLesson: regenerateMutation.isPending,
		isUpdatingProgress: progressMutation.isPending,

		// Error states
		completeError: completeMutation.error,
		nextPassError: nextPassMutation.error,
		regenerateError: regenerateMutation.error,
		progressError: progressMutation.error,
	}
}
