import { api } from "../../../lib/apiClient.js"

// Removed findModuleIdForLesson as it's no longer needed in the simplified backend
// where modules ARE lessons

/**
 * Fetch a specific lesson by lesson ID
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
