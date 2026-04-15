import { useCallback } from "react"
import { useCourseNavigation } from "@/utils/navigationUtils"
import { useLessonNextPassMutation } from "./use-lesson-data"

function normalizeAdaptiveLessonTarget(target) {
	if (!target || typeof target !== "object") {
		return null
	}

	const lessonId = target.lessonId ?? target.lesson?.id ?? target.id ?? null
	if (!lessonId) {
		return null
	}

	return {
		lessonId: String(lessonId),
		recommendedLessonEntry: target.recommendedLessonEntry === "start_next_pass" ? "start_next_pass" : "open_current",
	}
}

export function useAdaptiveLessonEntry(courseId) {
	const { goToLesson } = useCourseNavigation()
	const nextPassMutation = useLessonNextPassMutation(courseId)

	const openAdaptiveLesson = useCallback(
		async (target) => {
			const normalizedTarget = normalizeAdaptiveLessonTarget(target)
			if (!courseId || !normalizedTarget) {
				return null
			}

			if (normalizedTarget.recommendedLessonEntry === "start_next_pass") {
				const nextPassLesson = await nextPassMutation.mutateAsync({
					lessonId: normalizedTarget.lessonId,
					force: false,
				})

				const selectedVersionId = nextPassLesson?.versionId ?? null
				const currentVersionId = nextPassLesson?.currentVersionId ?? null
				const nextLessonId = nextPassLesson?.id ?? normalizedTarget.lessonId
				const query =
					selectedVersionId && currentVersionId && String(selectedVersionId) !== String(currentVersionId)
						? { versionId: selectedVersionId }
						: null

				goToLesson(courseId, nextLessonId, query)
				return nextPassLesson
			}

			goToLesson(courseId, normalizedTarget.lessonId)
			return normalizedTarget
		},
		[courseId, goToLesson, nextPassMutation]
	)

	return {
		openAdaptiveLesson,
		isOpeningAdaptiveLesson: nextPassMutation.isPending,
		openAdaptiveLessonError: nextPassMutation.error,
	}
}

export default useAdaptiveLessonEntry
