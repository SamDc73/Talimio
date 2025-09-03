import { useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useCourseNavigation } from "@/utils/navigationUtils"
import { useLessonCompleteMutation, useLessonProgressMutation } from "./useLessonData"

/**
 * Business logic actions for lessons
 * Following state management guide: "Model actions as events - business logic in hooks, not components"
 */
export function useLessonActions() {
	const navigate = useNavigate()
	const { goToLesson } = useCourseNavigation()
	const progressMutation = useLessonProgressMutation()
	const completeMutation = useLessonCompleteMutation()

	// Action: Navigate back from lesson
	const handleBack = useCallback(
		(courseId) => {
			if (courseId) {
				// Navigate to the course page if we have a course ID
				navigate(`/course/${courseId}`)
			} else {
				// Otherwise go back in history
				window.history.back()
			}
		},
		[navigate]
	)

	// Action: Navigate to another lesson
	const handleLessonNavigation = useCallback(
		(courseId, lessonId) => {
			if (courseId) {
				goToLesson(courseId, lessonId)
			} else {
				// Fallback to direct lesson navigation
				navigate(`/lesson/${lessonId}`)
			}
		},
		[navigate, goToLesson]
	)

	// Action: Mark lesson as complete
	const handleMarkComplete = useCallback(
		(lessonId) => {
			completeMutation.mutate(lessonId)

			// Emit event for cross-component communication
			// Following state management guide: "Event-Driven Updates"
			window.dispatchEvent(
				new CustomEvent("lessonComplete", {
					detail: { lessonId, timestamp: new Date().toISOString() },
				})
			)
		},
		[completeMutation]
	)

	// Action: Update lesson progress
	const handleProgressUpdate = useCallback(
		(lessonId, progressData) => {
			progressMutation.mutate({ lessonId, progressData })

			// Emit event for progress updates
			window.dispatchEvent(
				new CustomEvent("lessonProgressUpdate", {
					detail: { lessonId, progressData },
				})
			)
		},
		[progressMutation]
	)

	// Action: Regenerate lesson content
	const handleRegenerate = useCallback((lessonId) => {
		// This could trigger a mutation to regenerate content
		// For now, we'll emit an event
		window.dispatchEvent(
			new CustomEvent("lessonRegenerate", {
				detail: { lessonId },
			})
		)
	}, [])

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
