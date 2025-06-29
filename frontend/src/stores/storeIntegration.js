/**
 * Store Integration Helper
 *
 * This module provides unified hooks for working with the course store
 * and app store integration.
 */

import useAppStore from "./useAppStore.js";
import useCourseStore from "./useCourseStore.js";

/**
 * Initialize store integration
 * Call this once during app initialization
 */
export function initializeStoreIntegration() {
	// Make course store globally available for compatibility
	if (typeof window !== "undefined") {
		window.__courseStore = useCourseStore;
		console.log("Store integration initialized");
	}
}

/**
 * Create a unified hook that provides integrated store access
 *
 * @param {string} courseId - Optional course ID for scoped operations
 */
export function useUnifiedStore(courseId = null) {
	const appStore = useAppStore();
	const courseStore = useCourseStore();

	return {
		// App store access (for UI, preferences, books, videos)
		app: appStore,

		// Course store access (for courses, modules, lessons)
		course: courseStore,

		// Unified getters
		getActiveCourse: () => {
			return (
				courseStore.getActiveCourse() ||
				(appStore.getActiveCourse() ? { id: appStore.getActiveCourse() } : null)
			);
		},

		getCourseProgress: (id) => {
			const targetId = id || courseId;
			return targetId ? courseStore.getCourseProgress(targetId) : null;
		},

		getModules: (id) => {
			const targetId = id || courseId;
			return targetId ? courseStore.getModules(targetId) : [];
		},

		// Unified actions
		setActiveCourse: (id) => {
			courseStore.setActiveCourse(id);
			appStore.setActiveCourse(id); // Keep app store in sync
		},

		updateModuleStatus: (courseId, moduleId, status) => {
			courseStore.updateModuleStatus(courseId, moduleId, status);
		},
	};
}

/**
 * Hook specifically for course data
 */
export function useCourseData(courseId) {
	const courseStore = useCourseStore();
	const appStore = useAppStore();

	// Get course data from store
	const course = courseStore.getCourse(courseId);
	const modules = courseStore.getModules(courseId);
	const progress = courseStore.getCourseProgress(courseId);

	// Check if this is the active course
	const isActiveCourse = courseStore.courses.activeCourseId === courseId;
	const isActiveApp = appStore.getActiveCourse() === courseId;

	return {
		// Course data
		course,
		modules,
		progress,

		// Status flags
		hasData: !!course,
		isActive: isActiveCourse || isActiveApp,
		isLoading: courseStore.isCourseDataStale(courseId),

		// Actions
		setActive: () => courseStore.setActiveCourse(courseId),
		refresh: () => {
			// Trigger re-fetch from API
			courseStore.clearCourseCache(courseId);
		},
	};
}

/**
 * Hook for module data with progress tracking
 */
export function useModuleData(courseId, moduleId) {
	const courseStore = useCourseStore();

	const module = courseStore.getModule(courseId, moduleId);
	const lessons = courseStore.getLessons(moduleId);
	const progress = courseStore.getModuleProgress(courseId, moduleId);

	return {
		module,
		lessons,
		progress,

		// Actions
		updateStatus: (status) =>
			courseStore.updateModuleStatus(courseId, moduleId, status),
		setActive: () => courseStore.setActiveModule(moduleId),
	};
}

/**
 * Hook for lesson data with status tracking
 */
export function useLessonData(courseId, moduleId, lessonId) {
	const courseStore = useCourseStore();

	const lesson = courseStore.getLesson(moduleId, lessonId);
	const status = courseStore.getLessonStatus(moduleId, lessonId);

	return {
		lesson,
		status,

		// Actions
		updateStatus: (newStatus) =>
			courseStore.updateLessonStatus(courseId, moduleId, lessonId, newStatus),
		setActive: () => courseStore.setActiveLesson(lessonId),

		// Status helpers
		isCompleted: status.status === "done",
		isInProgress: status.status === "in_progress",
		isNotStarted: status.status === "not_started",
	};
}

// Export store instances for direct access when needed
export { useCourseStore, useAppStore };
