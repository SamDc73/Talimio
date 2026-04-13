import { api } from "@/lib/apiClient"

/**
 * Lesson-specific API functions
 * Following state management guide: separate API layer for each feature
 */

/**
 * Fetch a lesson using the canonical course endpoint.
 */
export async function fetchLesson(
	courseId,
	lessonId,
	{ generate = false, versionId = null, adaptiveFlow = false } = {}
) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required")
	}

	const queryParams = new URLSearchParams()
	if (generate) {
		queryParams.set("generate", "true")
	}
	if (versionId) {
		queryParams.set("versionId", versionId)
	}
	if (adaptiveFlow) {
		queryParams.set("adaptiveFlow", "true")
	}

	const query = queryParams.size > 0 ? `?${queryParams.toString()}` : ""
	return api.get(`/courses/${courseId}/lessons/${lessonId}${query}`)
}

export async function regenerateLesson(courseId, lessonId, { critiqueText, applyAcrossCourse = false }) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required")
	}

	const trimmedCritique = critiqueText?.trim()
	if (!trimmedCritique) {
		throw new Error("Regeneration request is required")
	}

	return api.post(`/courses/${courseId}/lessons/${lessonId}/regenerate`, {
		critiqueText: trimmedCritique,
		applyAcrossCourse,
	})
}

export async function startNextLessonPass(courseId, lessonId, { force = false } = {}) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required")
	}

	return api.post(`/courses/${courseId}/lessons/${lessonId}/next-pass`, {
		force,
	})
}
