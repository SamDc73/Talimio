import { api } from "@/lib/apiClient.js"

/**
 * Lesson-specific API functions
 * Following state management guide: separate API layer for each feature
 */

/**
 * Fetch a lesson by ID only (no courseId needed)
 * For simplified /lesson/:lessonId routing
 * This first discovers the course, then uses the proper hierarchical endpoint
 */
export async function fetchLessonById(lessonId) {
	if (!lessonId) {
		throw new Error("Lesson ID is required")
	}

	// First, get basic lesson info to find the course ID
	const basicLesson = await api.get(`/content/lessons/${lessonId}`)

	if (!basicLesson?.course_id) {
		throw new Error("Could not determine course ID for lesson")
	}

	// Now use the proper hierarchical endpoint with course context
	// This ensures we get the full lesson with generation support
	return api.get(`/courses/${basicLesson.course_id}/lessons/${lessonId}?generate=true`)
}

/**
 * Update lesson progress
 */
export async function updateLessonProgress(lessonId, progressData) {
	if (!lessonId) {
		throw new Error("Lesson ID is required")
	}

	return api.post(`/content/lessons/${lessonId}/progress`, progressData)
}

/**
 * Mark lesson as complete
 */
export async function markLessonComplete(lessonId) {
	if (!lessonId) {
		throw new Error("Lesson ID is required")
	}

	return api.post(`/content/lessons/${lessonId}/complete`)
}
