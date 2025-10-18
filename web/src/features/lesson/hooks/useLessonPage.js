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
export function useLessonPage(courseId, lessonId) {
	// Server state via React Query
	const { data: lesson, isLoading: lessonLoading, error: lessonError } = useLessonData(courseId, lessonId)

	// Resolve effective courseId using lesson payload fallback (course_id only)
	const resolvedCourseId = courseId ?? lesson?.course_id ?? null

	// Dependent queries - only fetch when we have courseId
	// Following state management guide: "Dependent queries - only fetch when ready"
	const { isLoading: courseLoading, course } = useCourseData(resolvedCourseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(resolvedCourseId)

	// Business logic actions
	const actions = useLessonActions(resolvedCourseId)

	// Computed values - don't store derived state
	// Following state management guide: "Computed Values Outside Store"
	const computedState = useMemo(
		() => ({
			// Loading states
			isDataLoading: lessonLoading || courseLoading || modulesLoading,

			// Course information
			courseName: course?.title || "Course",

			// Navigation handlers with pre-bound courseId
			handleBack: () => actions.handleBack(),
			handleLessonClick: (clickedLessonId) => actions.handleLessonNavigation(clickedLessonId),

			// Lesson actions with pre-bound lessonId
			handleMarkComplete: () => actions.handleMarkComplete(lessonId),
			handleRegenerate: () => actions.handleRegenerate(lessonId),

			// Error handling
			hasError: !!lessonError,
			errorMessage: lessonError?.message || "Failed to load lesson",
		}),
		[lessonLoading, courseLoading, modulesLoading, course?.title, actions, lessonId, lessonError]
	)

	return {
		// Data
		lesson,
		courseId: resolvedCourseId,
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
