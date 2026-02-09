import { api } from "@/lib/apiClient"

/**
 * Lesson-specific API functions
 * Following state management guide: separate API layer for each feature
 */

/**
 * Fetch a lesson using the canonical course endpoint.
 */
export async function fetchLesson(courseId, lessonId, { generate = false } = {}) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required")
	}

	const query = generate ? "?generate=true" : ""
	return api.get(`/courses/${courseId}/lessons/${lessonId}${query}`)
}

export function regenerateLesson(courseId, lessonId) {
	return fetchLesson(courseId, lessonId, { generate: true })
}
