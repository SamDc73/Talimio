/**
 * Course Progress Hook - Updated progress tracking for the unified course API
 *
 * This hook provides progress tracking functionality using the new
 * course → module → lesson structure instead of the legacy
 * roadmap → node structure.
 */

import {
	createContext,
	useContext,
	useEffect,
	useState,
	useCallback,
} from "react";
import { useCourseProgressService } from "../features/course";
import { useToast } from "./use-toast";

const CourseProgressContext = createContext(null);

/**
 * Course Progress Provider Component
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 * @param {string} props.courseId - The course ID
 */
export function CourseProgressProvider({ children, courseId }) {
	const [lessonStatuses, setLessonStatuses] = useState({});
	const [moduleProgress, setModuleProgress] = useState({});
	const [courseProgress, setCourseProgress] = useState({
		totalModules: 0,
		completedModules: 0,
		inProgressModules: 0,
		totalLessons: 0,
		completedLessons: 0,
		progressPercentage: 0,
	});
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);
	const { toast } = useToast();

	// Get progress service for this course
	const progressService = courseId ? useCourseProgressService(courseId) : null;

	/**
	 * Fetch all progress data for the course
	 */
	const fetchAllProgressData = useCallback(
		async (currentCourseId) => {
			if (!currentCourseId || !progressService) {
				console.log(
					"CourseProgressProvider - no courseId provided, skipping fetch",
				);
				setLessonStatuses({});
				setModuleProgress({});
				setCourseProgress({
					totalModules: 0,
					completedModules: 0,
					inProgressModules: 0,
					totalLessons: 0,
					completedLessons: 0,
					progressPercentage: 0,
				});
				return;
			}

			console.log(
				"CourseProgressProvider - starting data fetch for courseId:",
				currentCourseId,
			);
			setIsLoading(true);
			setError(null);

			try {
				// Fetch modules with their lesson progress
				const modulesWithProgress =
					await progressService.getCourseModulesWithProgress();

				// Transform data for easy lookup
				const statusMap = {};
				const moduleProgressMap = {};
				let totalLessons = 0;
				let completedLessons = 0;
				const totalModules = modulesWithProgress.length;
				let completedModules = 0;
				let inProgressModules = 0;

				for (const module of modulesWithProgress) {
					// Store module progress
					moduleProgressMap[module.id] = module.progress;

					// Count module completion
					if (module.progress.progressPercentage === 100) {
						completedModules++;
					} else if (module.progress.progressPercentage > 0) {
						inProgressModules++;
					}

					// Process lessons
					for (const lesson of module.lessons) {
						const lessonKey = `${module.id}:${lesson.id}`;
						statusMap[lessonKey] = lesson.progress?.status || "not_started";

						totalLessons++;
						if (lesson.progress?.status === "completed") {
							completedLessons++;
						}
					}
				}

				const progressPercentage =
					totalLessons > 0
						? Math.round((completedLessons / totalLessons) * 100)
						: 0;

				const progressData = {
					courseId: currentCourseId,
					totalModules,
					completedModules,
					inProgressModules,
					totalLessons,
					completedLessons,
					progressPercentage,
				};

				console.log("CourseProgressProvider - progress data:", progressData);

				setLessonStatuses(statusMap);
				setModuleProgress(moduleProgressMap);
				setCourseProgress(progressData);
			} catch (err) {
				console.error("CourseProgressProvider - fetch error:", err);
				setError(err);
				toast({
					title: "Error",
					description: err.message || "Failed to fetch progress data",
					variant: "destructive",
				});
			} finally {
				setIsLoading(false);
			}
		},
		[progressService, toast],
	);

	useEffect(() => {
		fetchAllProgressData(courseId);
	}, [courseId, fetchAllProgressData]);

	/**
	 * Toggle lesson completion status
	 */
	const toggleLessonCompletion = useCallback(
		async (moduleId, lessonId) => {
			if (!courseId || !progressService) return;

			const lessonKey = `${moduleId}:${lessonId}`;
			const originalLessonStatuses = { ...lessonStatuses };
			const originalCourseProgress = { ...courseProgress };
			const originalModuleProgress = { ...moduleProgress };

			try {
				const currentStatus = lessonStatuses[lessonKey] || "not_started";
				const newStatus =
					currentStatus === "completed" ? "not_started" : "completed";

				// Update UI immediately for better UX
				setLessonStatuses((prev) => ({
					...prev,
					[lessonKey]: newStatus,
				}));

				// Calculate optimistic progress updates
				const completedDelta = newStatus === "completed" ? 1 : -1;
				const newCompletedLessons = Math.max(
					0,
					courseProgress.completedLessons + completedDelta,
				);
				const newPercentage = Math.round(
					(newCompletedLessons / courseProgress.totalLessons) * 100,
				);

				setCourseProgress((prev) => ({
					...prev,
					completedLessons: newCompletedLessons,
					progressPercentage: newPercentage,
				}));

				// Update module progress optimistically
				const currentModuleProgress = moduleProgress[moduleId] || {
					totalLessons: 0,
					completedLessons: 0,
					inProgressLessons: 0,
					progressPercentage: 0,
				};

				const newModuleCompletedLessons = Math.max(
					0,
					currentModuleProgress.completedLessons + completedDelta,
				);
				const newModulePercentage =
					currentModuleProgress.totalLessons > 0
						? Math.round(
								(newModuleCompletedLessons /
									currentModuleProgress.totalLessons) *
									100,
							)
						: 0;

				setModuleProgress((prev) => ({
					...prev,
					[moduleId]: {
						...currentModuleProgress,
						completedLessons: newModuleCompletedLessons,
						progressPercentage: newModulePercentage,
					},
				}));

				// Update server in background
				await progressService.updateLessonStatus(moduleId, lessonId, newStatus);

				// Optionally refresh to ensure data consistency
				// await fetchAllProgressData(courseId);
			} catch (err) {
				console.error("Failed to update lesson status:", err);

				// Revert optimistic updates on error
				setLessonStatuses(originalLessonStatuses);
				setCourseProgress(originalCourseProgress);
				setModuleProgress(originalModuleProgress);

				toast({
					title: "Error updating lesson",
					description:
						"Failed to update lesson status. Your progress has been reverted.",
					variant: "destructive",
				});
			}
		},
		[
			courseId,
			progressService,
			lessonStatuses,
			courseProgress,
			moduleProgress,
			toast,
		],
	);

	/**
	 * Mark lesson as completed
	 */
	const markLessonCompleted = useCallback(
		async (moduleId, lessonId) => {
			if (!courseId || !progressService) return;

			const lessonKey = `${moduleId}:${lessonId}`;
			const originalLessonStatuses = { ...lessonStatuses };

			try {
				// Update UI immediately
				setLessonStatuses((prev) => ({
					...prev,
					[lessonKey]: "completed",
				}));

				// Update server
				await progressService.markLessonCompleted(moduleId, lessonId);

				// Refresh progress data
				await fetchAllProgressData(courseId);
			} catch (err) {
				console.error("Failed to mark lesson as completed:", err);
				setLessonStatuses(originalLessonStatuses);
				toast({
					title: "Error",
					description: "Failed to mark lesson as completed",
					variant: "destructive",
				});
			}
		},
		[courseId, progressService, lessonStatuses, fetchAllProgressData, toast],
	);

	/**
	 * Mark lesson as in progress
	 */
	const markLessonInProgress = useCallback(
		async (moduleId, lessonId) => {
			if (!courseId || !progressService) return;

			const lessonKey = `${moduleId}:${lessonId}`;
			const originalLessonStatuses = { ...lessonStatuses };

			try {
				// Update UI immediately
				setLessonStatuses((prev) => ({
					...prev,
					[lessonKey]: "in_progress",
				}));

				// Update server
				await progressService.markLessonInProgress(moduleId, lessonId);
			} catch (err) {
				console.error("Failed to mark lesson as in progress:", err);
				setLessonStatuses(originalLessonStatuses);
				toast({
					title: "Error",
					description: "Failed to update lesson status",
					variant: "destructive",
				});
			}
		},
		[courseId, progressService, lessonStatuses, toast],
	);

	/**
	 * Check if a lesson is completed
	 */
	const isLessonCompleted = useCallback(
		(moduleId, lessonId) => {
			const lessonKey = `${moduleId}:${lessonId}`;
			return lessonStatuses[lessonKey] === "completed";
		},
		[lessonStatuses],
	);

	/**
	 * Get lesson status
	 */
	const getLessonStatus = useCallback(
		(moduleId, lessonId) => {
			const lessonKey = `${moduleId}:${lessonId}`;
			return lessonStatuses[lessonKey] || "not_started";
		},
		[lessonStatuses],
	);

	/**
	 * Get module progress
	 */
	const getModuleProgress = useCallback(
		(moduleId) => {
			return (
				moduleProgress[moduleId] || {
					totalLessons: 0,
					completedLessons: 0,
					inProgressLessons: 0,
					progressPercentage: 0,
				}
			);
		},
		[moduleProgress],
	);

	/**
	 * Refresh all progress data
	 */
	const refreshProgress = useCallback(() => {
		return fetchAllProgressData(courseId);
	}, [fetchAllProgressData, courseId]);

	const value = {
		// State
		lessonStatuses,
		moduleProgress,
		courseProgress,
		isLoading,
		error,

		// Actions
		toggleLessonCompletion,
		markLessonCompleted,
		markLessonInProgress,
		refreshProgress,

		// Getters
		isLessonCompleted,
		getLessonStatus,
		getModuleProgress,

		// Legacy compatibility (for gradual migration)
		fetchAllProgressData,
	};

	return (
		<CourseProgressContext.Provider value={value}>
			{children}
		</CourseProgressContext.Provider>
	);
}

/**
 * Hook to use course progress context
 */
export function useCourseProgress() {
	const context = useContext(CourseProgressContext);
	if (context === null) {
		throw new Error(
			"useCourseProgress must be used within a CourseProgressProvider",
		);
	}
	return context;
}

/**
 * Hook that safely uses course progress context
 * Returns null values if not in a provider
 */
export function useCourseProgressSafe() {
	const context = useContext(CourseProgressContext);
	if (context === null) {
		return {
			lessonStatuses: {},
			moduleProgress: {},
			courseProgress: {
				totalModules: 0,
				completedModules: 0,
				inProgressModules: 0,
				totalLessons: 0,
				completedLessons: 0,
				progressPercentage: 0,
			},
			isLoading: false,
			error: null,
			toggleLessonCompletion: () => {},
			markLessonCompleted: () => {},
			markLessonInProgress: () => {},
			isLessonCompleted: () => false,
			getLessonStatus: () => "not_started",
			getModuleProgress: () => ({
				totalLessons: 0,
				completedLessons: 0,
				inProgressLessons: 0,
				progressPercentage: 0,
			}),
			refreshProgress: () => Promise.resolve(),
		};
	}
	return context;
}

/**
 * Legacy compatibility hook that wraps both old and new progress systems
 */
export function useUnifiedProgress(_courseId, legacyMode = false) {
	const courseProgress = useCourseProgressSafe();

	// Legacy mode would use the old useProgress hook
	if (legacyMode) {
		// Import legacy hook dynamically to avoid issues
		const { useProgressSafe } = require("./useProgress");
		const legacyProgress = useProgressSafe();

		return {
			...legacyProgress,
			isLegacyMode: true,
			isNewMode: false,
		};
	}

	return {
		...courseProgress,
		isLegacyMode: false,
		isNewMode: true,
	};
}

/**
 * Utility to convert between legacy and new progress formats
 */
export const progressUtils = {
	/**
	 * Convert legacy lesson ID to module:lesson format
	 */
	convertLegacyLessonId(nodeId, moduleId) {
		return `${moduleId}:${nodeId}`;
	},

	/**
	 * Extract module and lesson IDs from new format
	 */
	parseLessonKey(lessonKey) {
		const [moduleId, lessonId] = lessonKey.split(":");
		return { moduleId, lessonId };
	},

	/**
	 * Convert legacy status to new status
	 */
	convertLegacyStatus(legacyStatus) {
		switch (legacyStatus) {
			case "done":
				return "completed";
			case "in_progress":
				return "in_progress";
			default:
				return "not_started";
		}
	},

	/**
	 * Convert new status to legacy status
	 */
	convertNewStatus(newStatus) {
		switch (newStatus) {
			case "completed":
				return "done";
			case "in_progress":
				return "in_progress";
			default:
				return "not_started";
		}
	},
};
