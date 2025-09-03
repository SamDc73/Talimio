import { api } from "@/lib/apiClient.js"

/**
 * Lesson-specific API functions
 * Following state management guide: separate API layer for each feature
 */

/**
 * Fetch a lesson by ID only (no courseId needed)
 * For simplified /lesson/:lessonId routing
 */
export async function fetchLessonById(lessonId) {
	if (!lessonId) {
		throw new Error("Lesson ID is required")
	}

	// Use centralized API client with deduplication
	return api.get(`/content/lessons/${lessonId}?generate=true`)
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
