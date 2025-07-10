const BASE = import.meta.env.VITE_API_BASE || "/api/v1";

// Removed findModuleIdForLesson as it's no longer needed in the simplified backend
// where modules ARE lessons

/**
 * Fetch a specific lesson by just lesson ID (optimized lookup)
 */
export async function fetchLesson(courseId, lessonId) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required");
	}

	// In the simplified backend, modules ARE lessons, so we use the simplified endpoint
	// that treats lesson_id as a module/node ID
	const res = await fetch(
		`${BASE}/courses/${courseId}/lessons/${lessonId}?generate=true`,
	);
	if (!res.ok) {
		throw new Error(`Failed to fetch lesson: ${res.status}`);
	}
	return res.json();
}

/**
 * Fetch a specific lesson by IDs (full endpoint, fallback)
 */
export async function fetchLessonFull(courseId, moduleId, lessonId) {
	if (!courseId || !moduleId || !lessonId) {
		throw new Error("Course ID, Module ID, and Lesson ID are required");
	}

	// The backend endpoint accepts the module_id in the path but actually uses lesson_id
	// In our simplified system, modules ARE lessons, so lesson_id is what matters
	const res = await fetch(
		`${BASE}/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}?generate=true`,
	);
	if (!res.ok) {
		throw new Error(`Failed to fetch lesson: ${res.status}`);
	}
	return res.json();
}

/**
 * Fetch all lessons for a module
 */
export async function fetchLessons(courseId, moduleId) {
	if (!courseId || !moduleId) {
		throw new Error("Course ID and Module ID are required");
	}

	const res = await fetch(
		`${BASE}/courses/${courseId}/modules/${moduleId}/lessons`,
	);
	if (!res.ok) {
		throw new Error(`Failed to fetch lessons: ${res.status}`);
	}
	return res.json();
}

/**
 * Generate a new lesson
 */
export async function generateLesson(courseId, moduleId) {
	if (!courseId || !moduleId) {
		throw new Error("Course ID and Module ID are required");
	}

	const res = await fetch(
		`${BASE}/courses/${courseId}/modules/${moduleId}/lessons`,
		{
			method: "POST",
			headers: { "Content-Type": "application/json" },
		},
	);
	if (!res.ok) {
		throw new Error(`Failed to generate lesson: ${res.status}`);
	}
	return res.json();
}
