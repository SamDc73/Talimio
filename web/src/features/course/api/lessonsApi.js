import { api } from "../../../lib/apiClient.js"

// Removed findModuleIdForLesson as it's no longer needed in the simplified backend
// where modules ARE lessons

/**
 * Fetch a specific lesson by just lesson ID (optimized lookup)
 * Uses centralized API client with deduplication for identical requests
 */
export async function fetchLesson(courseId, lessonId) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required")
	}

	// Use centralized API client with automatic deduplication
	// Multiple concurrent calls to the same lesson will share the same promise
	const endpoint = `/courses/${courseId}/lessons/${lessonId}?generate=true`
	return api.get(endpoint)
}

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
 * Fetch a specific lesson by IDs (full endpoint, fallback)
 */
export async function fetchLessonFull(courseId, moduleId, lessonId) {
	if (!courseId || !moduleId || !lessonId) {
		throw new Error("Course ID, Module ID, and Lesson ID are required")
	}

	// Use centralized API client with deduplication
	// The backend endpoint accepts the module_id in the path but actually uses lesson_id
	// In our simplified system, modules ARE lessons, so lesson_id is what matters
	return api.get(`/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}?generate=true`)
}

/**
 * Fetch all lessons for a module
 */
export async function fetchLessons(courseId, moduleId) {
	if (!courseId || !moduleId) {
		throw new Error("Course ID and Module ID are required")
	}

	// Use centralized API client with deduplication
	return api.get(`/courses/${courseId}/modules/${moduleId}/lessons`)
}

/**
 * Generate a new lesson
 */
export async function generateLesson(courseId, moduleId) {
	if (!courseId || !moduleId) {
		throw new Error("Course ID and Module ID are required")
	}

	// Use centralized API client (POST requests are not deduplicated)
	return api.post(`/courses/${courseId}/modules/${moduleId}/lessons`)
}
