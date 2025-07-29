import { useCallback, useMemo, useRef } from "react";
import { useProgress, useUpdateProgress } from "./useProgress";

/**
 * Adapter hook for backward compatibility with course progress
 * Maps the new unified progress API to the old course-specific interface
 */
export function useCourseProgress(courseId) {
	// Memoize the contentIds array to prevent unnecessary re-queries
	const contentIds = useMemo(() => (courseId ? [courseId] : []), [courseId]);

	const progressQuery = useProgress(contentIds);
	const updateProgress = useUpdateProgress();

	// Use refs to store functions that don't need to trigger re-renders
	const refetchRef = useRef(progressQuery.refetch);
	refetchRef.current = progressQuery.refetch;

	// Get the current progress data from the map
	const currentProgress = progressQuery.data?.[courseId] || 0;
	const rawMetadata = progressQuery.metadata?.[courseId] || {};

	// Extract values with defaults
	const completedLessonsArray = rawMetadata.completed_lessons || [];
	const currentLessonId = rawMetadata.current_lesson_id;
	const totalLessons = rawMetadata.total_lessons || 0;

	// Helper to calculate progress from completed lessons
	const calculateProgressFromLessons = useCallback(
		(completedLessons, totalLessons) => {
			if (!totalLessons || totalLessons === 0) return 0;
			return Math.round((completedLessons.length / totalLessons) * 100);
		},
		[],
	);

	// Check if a specific lesson is completed
	const isCompleted = (lessonId) => {
		return completedLessonsArray.includes(String(lessonId));
	};

	// Toggle lesson completion
	const toggleCompletion = useCallback(
		async (lessonId, totalLessonsOverride) => {
			const lessonIdStr = String(lessonId);
			let newCompletedLessons;

			if (completedLessonsArray.includes(lessonIdStr)) {
				// Remove from completed
				newCompletedLessons = completedLessonsArray.filter(
					(id) => id !== lessonIdStr,
				);
			} else {
				// Add to completed
				newCompletedLessons = [...completedLessonsArray, lessonIdStr];
			}

			// Use override if provided (from CourseSidebar which knows the actual lesson count)
			const actualTotalLessons = totalLessonsOverride || totalLessons;

			// Calculate new progress based on completed lessons
			const newProgress = calculateProgressFromLessons(
				newCompletedLessons,
				actualTotalLessons,
			);

			await updateProgress.mutateAsync({
				contentId: courseId,
				progress: newProgress,
				metadata: {
					content_type: "course",
					completed_lessons: newCompletedLessons,
					current_lesson_id: lessonIdStr,
					total_lessons: actualTotalLessons,
				},
			});
		},
		[
			courseId,
			completedLessonsArray,
			totalLessons,
			calculateProgressFromLessons,
			updateProgress,
		],
	);

	return {
		progress: {
			percentage: currentProgress,
			value: currentProgress, // Alias for compatibility
		},
		metadata: {
			completedLessons: completedLessonsArray,
			currentLessonId,
			totalLessons,
		},
		isLoading: progressQuery.isLoading,
		loading: progressQuery.isLoading, // Legacy alias
		error: progressQuery.error,
		refetch: () => refetchRef.current(),
		isCompleted,
		toggleCompletion,
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: courseId,
				progress,
				metadata: {
					content_type: "course",
					completed_lessons: completedLessonsArray,
					current_lesson_id: currentLessonId,
					total_lessons: totalLessons,
					...metadata,
				},
			}),
		// Legacy method names for compatibility
		setProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: courseId,
				progress,
				metadata: {
					content_type: "course",
					completed_lessons: completedLessonsArray,
					current_lesson_id: currentLessonId,
					total_lessons: totalLessons,
					...metadata,
				},
			}),
	};
}

/**
 * Hook for updating course-specific metadata along with progress
 */
export function useCourseProgressWithLessons(courseId) {
	const updateProgress = useUpdateProgress();
	const { progress, isLoading, error } = useCourseProgress(courseId);

	const updateCourseProgress = (completedLessons, totalLessons) => {
		const progressPercentage =
			totalLessons > 0 ? (completedLessons / totalLessons) * 100 : 0;

		updateProgress.mutate({
			contentId: courseId,
			progress: progressPercentage,
			metadata: {
				content_type: "course",
				completed_lessons: completedLessons,
				total_lessons: totalLessons,
			},
		});
	};

	return {
		progress: {
			percentage: progress.percentage,
			value: progress.percentage,
		},
		isLoading,
		error,
		updateCourseProgress,
		updateLessons: (completed, total) => updateCourseProgress(completed, total),
	};
}
