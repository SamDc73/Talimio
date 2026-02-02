import { useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useCourseNavigation } from "@/utils/navigationUtils"
import { useLessonCompleteMutation, useLessonProgressMutation } from "./useLessonData"

/**
 * Business logic actions for lessons
 * Following state management guide: "Model actions as events - business logic in hooks, not components"
 */
export function useLessonActions(courseId) {
	const navigate = useNavigate()
	const { goToLesson } = useCourseNavigation()
	const progressMutation = useLessonProgressMutation(courseId)
	const completeMutation = useLessonCompleteMutation(courseId)

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
		(lessonId, targetCourseId) => {
			const courseToUse = targetCourseId ?? courseId
			if (!courseToUse || !lessonId) {
				return
			}

			// This could trigger a mutation to regenerate content
			// For now, we'll emit an event
			window.dispatchEvent(
				new CustomEvent("lessonRegenerate", {
					detail: { courseId: courseToUse, lessonId },
				})
			)
		},
		[courseId]
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

		// Mutation states for UI feedback
		isCompletingLesson: completeMutation.isPending,
		isUpdatingProgress: progressMutation.isPending,

		// Error states
		completeError: completeMutation.error,
		progressError: progressMutation.error,
	}
}
