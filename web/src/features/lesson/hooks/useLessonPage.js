import { useMemo } from "react"
import { useCourseData } from "@/features/course/hooks/useCourseData"
import { useOutlineData } from "@/features/course/hooks/useOutlineData"
import { useLessonActions } from "./useLessonActions"
import { useLessonData } from "./useLessonData"

/**
 * Combined hook for LessonPage
 * Following state management guide: "Combine stores via custom hooks"
 *
 * This hook combines all the data and actions needed for the lesson page,
 * keeping the component simple and focused on rendering.
 */
export function useLessonPage(lessonId) {
	// Server state via React Query
	const { data: lesson, isLoading: lessonLoading, error: lessonError } = useLessonData(lessonId)

	// Derive courseId from lesson data
	const courseId = lesson?.roadmap_id || lesson?.course_id

	// Dependent queries - only fetch when we have courseId
	// Following state management guide: "Dependent queries - only fetch when ready"
	const { isLoading: roadmapLoading, roadmap } = useCourseData(courseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)

	// Business logic actions
	const actions = useLessonActions()

	// Computed values - don't store derived state
	// Following state management guide: "Computed Values Outside Store"
	const computedState = useMemo(
		() => ({
			// Loading states
			isDataLoading: lessonLoading || roadmapLoading || modulesLoading,

			// Course information
			courseName: roadmap?.title || "Course",

			// Navigation handlers with pre-bound courseId
			handleBack: () => actions.handleBack(courseId),
			handleLessonClick: (clickedLessonId) => actions.handleLessonNavigation(courseId, clickedLessonId),

			// Lesson actions with pre-bound lessonId
			handleMarkComplete: () => actions.handleMarkComplete(lessonId),
			handleRegenerate: () => actions.handleRegenerate(lessonId),

			// Error handling
			hasError: !!lessonError,
			errorMessage: lessonError?.message || "Failed to load lesson",
		}),
		[lessonLoading, roadmapLoading, modulesLoading, roadmap?.title, actions, courseId, lessonId, lessonError]
	)

	return {
		// Data
		lesson,
		courseId,
		modules: modules || [],

		// Computed state
		...computedState,

		// Raw action handlers for advanced use cases
		actions,

		// Loading and error states
		isLoading: computedState.isDataLoading,
		error: lessonError,
	}
}
