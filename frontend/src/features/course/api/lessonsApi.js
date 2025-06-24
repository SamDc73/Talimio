const BASE = import.meta.env.VITE_API_BASE || "/api/v1";
import { getCourseWithModules } from "@/utils/courseDetection";

/**
 * Find moduleId for a lesson by using cached course data (more efficient)
 */
async function findModuleIdForLesson(courseId, lessonId) {
	try {
		// Use the cached getCourseWithModules which is more efficient
		const { modules } = await getCourseWithModules(courseId);

		const findParentModuleId = (modulesToSearch, id) => {
			for (const module of modulesToSearch) {
				if (module.lessons?.some((lesson) => lesson.id === id)) {
					return module.id;
				}

				if (module.lessons) {
					const parentId = findParentModuleId(module.lessons, id);
					if (parentId) {
						return parentId;
					}
				}
			}
			return null;
		};

		return findParentModuleId(modules, lessonId);
	} catch (err) {
		console.error("Error finding module for lesson:", err);
		return null;
	}
}

/**
 * Fetch a specific lesson by just lesson ID (optimized lookup)
 */
export async function fetchLesson(courseId, lessonId) {
	if (!courseId || !lessonId) {
		throw new Error("Course ID and Lesson ID are required");
	}

	// Try to find the moduleId for this lesson using efficient method
	const moduleId = await findModuleIdForLesson(courseId, lessonId);
	if (!moduleId) {
		throw new Error(`Could not find module for lesson ${lessonId} in course ${courseId}`);
	}

	// Use the full endpoint with moduleId
	return fetchLessonFull(courseId, moduleId, lessonId);
}

/**
 * Fetch a specific lesson by IDs (full endpoint, fallback)
 */
export async function fetchLessonFull(courseId, moduleId, lessonId) {
	if (!courseId || !moduleId || !lessonId) {
		throw new Error("Course ID, Module ID, and Lesson ID are required");
	}

	const res = await fetch(`${BASE}/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}?generate=true`);
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

	const res = await fetch(`${BASE}/courses/${courseId}/modules/${moduleId}/lessons`);
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

	const res = await fetch(`${BASE}/courses/${courseId}/modules/${moduleId}/lessons`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
	});
	if (!res.ok) {
		throw new Error(`Failed to generate lesson: ${res.status}`);
	}
	return res.json();
}
