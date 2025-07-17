/**
 * Course Progress Service - Unified progress tracking for the new course API
 *
 * This service handles progress tracking using the new course → module → lesson
 * structure instead of the legacy roadmap → node structure.
 */

import { useCourseService } from "./courseApi";

/**
 * Base API URL for progress endpoints
 */
const API_BASE = "/api/v1";

/**
 * Default timeout for API requests in milliseconds
 */
const REQUEST_TIMEOUT = 7000;

/**
 * Cache configuration
 */
const CACHE_CONFIG = {
	maxAge: 5 * 60 * 1000, // 5 minutes
	maxSize: 1000, // Maximum number of items to cache
};

/**
 * Simple in-memory cache implementation
 */
class Cache {
	constructor(maxAge, maxSize) {
		this.maxAge = maxAge;
		this.maxSize = maxSize;
		this.cache = new Map();
	}

	set(key, value) {
		if (this.cache.size >= this.maxSize) {
			// Remove oldest entry
			const oldestKey = this.cache.keys().next().value;
			this.cache.delete(oldestKey);
		}
		this.cache.set(key, {
			value,
			timestamp: Date.now(),
		});
	}

	get(key) {
		const entry = this.cache.get(key);
		if (!entry) return null;

		if (Date.now() - entry.timestamp > this.maxAge) {
			this.cache.delete(key);
			return null;
		}

		return entry.value;
	}

	clear() {
		this.cache.clear();
	}

	delete(key) {
		this.cache.delete(key);
	}
}

// Initialize cache
const progressCache = new Cache(CACHE_CONFIG.maxAge, CACHE_CONFIG.maxSize);

/**
 * Fetch with timeout wrapper
 */
async function fetchWithTimeout(url, options = {}) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
		});
		clearTimeout(timeout);
		return response;
	} catch (error) {
		clearTimeout(timeout);
		if (error.name === "AbortError") {
			throw new Error(`Request timeout after ${REQUEST_TIMEOUT}ms`);
		}
		throw error;
	}
}

/**
 * Service class for course progress operations
 */
export class CourseProgressService {
	constructor(courseId, courseService) {
		this.courseId = courseId;
		this.courseService = courseService;
	}

	/**
	 * Get overall progress for the course
	 */
	async getCourseProgress() {
		const cacheKey = `course-progress-${this.courseId}`;
		const cachedData = progressCache.get(cacheKey);
		if (cachedData) {
			return cachedData;
		}

		try {
			const progress = await this.courseService.fetchCourseProgress();
			progressCache.set(cacheKey, progress);
			return progress;
		} catch (error) {
			console.error("Error fetching course progress:", error);
			throw error;
		}
	}

	/**
	 * Get lesson status
	 */
	async getLessonStatus(moduleId, lessonId) {
		const cacheKey = `lesson-status-${this.courseId}-${moduleId}-${lessonId}`;
		const cachedData = progressCache.get(cacheKey);
		if (cachedData) {
			return cachedData;
		}

		try {
			const status = await this.courseService.fetchLessonStatus(
				moduleId,
				lessonId,
			);
			progressCache.set(cacheKey, status);
			return status;
		} catch (error) {
			console.error("Error fetching lesson status:", error);
			throw error;
		}
	}

	/**
	 * Update lesson status
	 */
	async updateLessonStatus(moduleId, lessonId, status) {
		try {
			const result = await this.courseService.updateLessonStatus(
				moduleId,
				lessonId,
				status,
			);

			// Invalidate relevant cache entries
			this.invalidateProgressCache(moduleId, lessonId);

			return result;
		} catch (error) {
			console.error("Error updating lesson status:", error);
			throw error;
		}
	}

	/**
	 * Get all lessons with their statuses for a module
	 */
	async getModuleLessonsWithProgress(moduleId) {
		const cacheKey = `module-lessons-progress-${this.courseId}-${moduleId}`;
		const cachedData = progressCache.get(cacheKey);
		if (cachedData) {
			return cachedData;
		}

		try {
			// Fetch lessons for the module
			const lessons = await this.courseService.fetchLessons(moduleId);

			// Fetch status for each lesson
			const lessonsWithProgress = await Promise.all(
				lessons.map(async (lesson) => {
					try {
						const status = await this.getLessonStatus(moduleId, lesson.id);
						return {
							...lesson,
							progress: status,
						};
					} catch (error) {
						// If status fetch fails, assume not started
						console.warn(
							`Failed to fetch status for lesson ${lesson.id}:`,
							error,
						);
						return {
							...lesson,
							progress: {
								status: "not_started",
								lesson_id: lesson.id,
								module_id: moduleId,
								course_id: this.courseId,
								created_at: new Date().toISOString(),
								updated_at: new Date().toISOString(),
							},
						};
					}
				}),
			);

			progressCache.set(cacheKey, lessonsWithProgress);
			return lessonsWithProgress;
		} catch (error) {
			console.error("Error fetching module lessons with progress:", error);
			throw error;
		}
	}

	/**
	 * Get all modules with their lesson progress
	 */
	async getCourseModulesWithProgress() {
		const cacheKey = `course-modules-progress-${this.courseId}`;
		const cachedData = progressCache.get(cacheKey);
		if (cachedData) {
			return cachedData;
		}

		try {
			// Fetch modules for the course
			const modules = await this.courseService.fetchModules();

			// Fetch lessons and progress for each module
			const modulesWithProgress = await Promise.all(
				modules.map(async (module) => {
					try {
						const lessonsWithProgress = await this.getModuleLessonsWithProgress(
							module.id,
						);

						// Calculate module progress
						const totalLessons = lessonsWithProgress.length;
						const completedLessons = lessonsWithProgress.filter(
							(lesson) => lesson.progress?.status === "completed",
						).length;
						const inProgressLessons = lessonsWithProgress.filter(
							(lesson) => lesson.progress?.status === "in_progress",
						).length;

						const progressPercentage =
							totalLessons > 0
								? Math.round((completedLessons / totalLessons) * 100)
								: 0;

						return {
							...module,
							lessons: lessonsWithProgress,
							progress: {
								totalLessons,
								completedLessons,
								inProgressLessons,
								progressPercentage,
							},
						};
					} catch (error) {
						console.warn(
							`Failed to fetch progress for module ${module.id}:`,
							error,
						);
						return {
							...module,
							lessons: [],
							progress: {
								totalLessons: 0,
								completedLessons: 0,
								inProgressLessons: 0,
								progressPercentage: 0,
							},
						};
					}
				}),
			);

			progressCache.set(cacheKey, modulesWithProgress);
			return modulesWithProgress;
		} catch (error) {
			console.error("Error fetching course modules with progress:", error);
			throw error;
		}
	}

	/**
	 * Toggle lesson completion status
	 */
	async toggleLessonCompletion(moduleId, lessonId) {
		try {
			// Get current status
			const currentStatus = await this.getLessonStatus(moduleId, lessonId);
			const newStatus =
				currentStatus.status === "completed" ? "not_started" : "completed";

			// Update status
			return await this.updateLessonStatus(moduleId, lessonId, newStatus);
		} catch (error) {
			console.error("Error toggling lesson completion:", error);
			throw error;
		}
	}

	/**
	 * Mark lesson as in progress
	 */
	async markLessonInProgress(moduleId, lessonId) {
		return await this.updateLessonStatus(moduleId, lessonId, "in_progress");
	}

	/**
	 * Mark lesson as completed
	 */
	async markLessonCompleted(moduleId, lessonId) {
		return await this.updateLessonStatus(moduleId, lessonId, "completed");
	}

	/**
	 * Reset lesson progress
	 */
	async resetLessonProgress(moduleId, lessonId) {
		return await this.updateLessonStatus(moduleId, lessonId, "not_started");
	}

	/**
	 * Invalidate cache entries related to progress
	 */
	invalidateProgressCache(moduleId = null, lessonId = null) {
		if (lessonId && moduleId) {
			// Invalidate specific lesson status cache
			progressCache.delete(
				`lesson-status-${this.courseId}-${moduleId}-${lessonId}`,
			);
		}

		if (moduleId) {
			// Invalidate module lessons progress cache
			progressCache.delete(
				`module-lessons-progress-${this.courseId}-${moduleId}`,
			);
		}

		// Invalidate course-level caches
		progressCache.delete(`course-progress-${this.courseId}`);
		progressCache.delete(`course-modules-progress-${this.courseId}`);
	}

	/**
	 * Clear all progress cache
	 */
	clearCache() {
		progressCache.clear();
	}
}

/**
 * Hook for course progress operations
 */
export function useCourseProgressService(courseId) {
	const courseService = useCourseService(courseId);

	if (!courseId) {
		throw new Error("Course ID is required for progress service");
	}

	return new CourseProgressService(courseId, courseService);
}

/**
 * Legacy compatibility functions for gradual migration
 */

/**
 * Convert legacy node-based progress to course-based progress
 */
export function convertLegacyProgressToCourse(
	legacyProgress,
	courseId,
	moduleId,
) {
	return {
		lesson_id: legacyProgress.nodeId,
		module_id: moduleId,
		course_id: courseId,
		status:
			legacyProgress.status === "done"
				? "completed"
				: legacyProgress.status === "in_progress"
					? "in_progress"
					: "not_started",
		created_at: legacyProgress.createdAt || new Date().toISOString(),
		updated_at: legacyProgress.updatedAt || new Date().toISOString(),
	};
}

/**
 * Convert course-based progress to legacy format
 */
export function convertCourseProgressToLegacy(courseProgress) {
	return {
		nodeId: courseProgress.lesson_id,
		status:
			courseProgress.status === "completed" ? "done" : courseProgress.status,
		createdAt: courseProgress.created_at,
		updatedAt: courseProgress.updated_at,
	};
}

/**
 * Direct API functions for compatibility with existing code
 */

/**
 * Get course progress using direct API calls
 */
export async function getCourseProgressDirect(courseId) {
	const cacheKey = `course-progress-${courseId}`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/progress`,
		);
		if (!response.ok) {
			throw new Error(
				`Failed to fetch course progress: ${response.statusText}`,
			);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching course progress:", error);
		throw error;
	}
}

/**
 * Update lesson status using direct API calls
 */
export async function updateLessonStatusDirect(
	courseId,
	moduleId,
	lessonId,
	status,
) {
	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/status`,
			{
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ status }),
			},
		);

		if (!response.ok) {
			throw new Error(`Failed to update lesson status: ${response.statusText}`);
		}
		const data = await response.json();

		// Invalidate relevant cache entries
		progressCache.delete(`lesson-status-${courseId}-${moduleId}-${lessonId}`);
		progressCache.delete(`module-lessons-progress-${courseId}-${moduleId}`);
		progressCache.delete(`course-progress-${courseId}`);
		progressCache.delete(`course-modules-progress-${courseId}`);

		return data;
	} catch (error) {
		console.error("Error updating lesson status:", error);
		throw error;
	}
}

/**
 * Get lesson status using direct API calls
 */
export async function getLessonStatusDirect(courseId, moduleId, lessonId) {
	const cacheKey = `lesson-status-${courseId}-${moduleId}-${lessonId}`;
	const cachedData = progressCache.get(cacheKey);
	if (cachedData) {
		return cachedData;
	}

	try {
		const response = await fetchWithTimeout(
			`${API_BASE}/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/status`,
		);
		if (!response.ok) {
			throw new Error(`Failed to fetch lesson status: ${response.statusText}`);
		}
		const data = await response.json();
		progressCache.set(cacheKey, data);
		return data;
	} catch (error) {
		console.error("Error fetching lesson status:", error);
		throw error;
	}
}

// Export cache for testing
export const _progressCache = progressCache;
