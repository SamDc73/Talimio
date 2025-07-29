import { useCallback, useMemo, useRef } from "react";
import { useProgress, useUpdateProgress } from "./useProgress";

/**
 * Adapter hook for backward compatibility with video progress
 * Maps the new unified progress API to the old video-specific interface
 */
export function useVideoProgress(videoId) {
	// Memoize the contentIds array to prevent unnecessary re-queries
	const contentIds = useMemo(() => (videoId ? [videoId] : []), [videoId]);

	const progressQuery = useProgress(contentIds);
	const updateProgress = useUpdateProgress();

	// Use refs to store functions that don't need to trigger re-renders
	const refetchRef = useRef(progressQuery.refetch);
	refetchRef.current = progressQuery.refetch;

	// Get the current progress data from the map
	const currentProgress = progressQuery.data?.[videoId] || 0;
	const rawMetadata = progressQuery.metadata?.[videoId] || {};

	// Extract values with defaults
	const completedChapters = rawMetadata.completedChapters || {};
	const totalChapters = rawMetadata.totalChapters || 0;

	// Check if a specific chapter is completed
	const isCompleted = useCallback(
		(chapterId) => {
			return completedChapters[chapterId] === true;
		},
		[completedChapters],
	);

	// Toggle chapter completion
	const toggleCompletion = useCallback(
		async (chapterId, totalChaptersOverride) => {
			const currentCompleted = completedChapters[chapterId] || false;
			const newCompletedChapters = {
				...completedChapters,
				[chapterId]: !currentCompleted,
			};

			// Use override if provided (from VideoSidebar which knows the actual chapter count)
			const actualTotalChapters =
				totalChaptersOverride ||
				totalChapters ||
				Object.keys(completedChapters).length;

			// Calculate progress based on completed chapters
			let newProgress = currentProgress;
			if (actualTotalChapters && actualTotalChapters > 0) {
				const completedCount =
					Object.values(newCompletedChapters).filter(Boolean).length;
				newProgress = Math.round((completedCount / actualTotalChapters) * 100);
			}

			// Update both progress and metadata (only send necessary fields)
			await updateProgress.mutateAsync({
				contentId: videoId,
				progress: newProgress,
				metadata: {
					content_type: "video",
					completedChapters: newCompletedChapters,
					totalChapters: actualTotalChapters,
				},
			});

			// Return the new state for immediate UI update
			return !currentCompleted;
		},
		[
			videoId,
			currentProgress,
			totalChapters,
			completedChapters,
			updateProgress,
		],
	);

	// Method to set total chapters (needed for progress calculation)
	const setTotalChapters = useCallback(
		async (newTotalChapters) => {
			await updateProgress.mutateAsync({
				contentId: videoId,
				progress: currentProgress,
				metadata: {
					content_type: "video",
					completedChapters,
					totalChapters: newTotalChapters,
				},
			});
		},
		[videoId, currentProgress, completedChapters, updateProgress],
	);

	return {
		progress: {
			percentage: currentProgress,
			value: currentProgress, // Alias for compatibility
		},
		metadata: {
			completedChapters,
			totalChapters,
		},
		isLoading: progressQuery.isLoading,
		loading: progressQuery.isLoading, // Legacy alias
		error: progressQuery.error,
		refetch: () => refetchRef.current(),
		isCompleted,
		toggleCompletion,
		setTotalChapters,
		completedChapters, // Legacy direct access
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: videoId,
				progress,
				metadata: {
					content_type: "video",
					...metadata,
				},
			}),
		// Legacy method names for compatibility
		setProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: videoId,
				progress,
				metadata: {
					content_type: "video",
					...metadata,
				},
			}),
	};
}

/**
 * Hook for updating video-specific metadata along with progress
 */
export function useVideoProgressWithPosition(videoId) {
	const updateProgress = useUpdateProgress();
	const { progress, isLoading, error } = useVideoProgress(videoId);

	const updateVideoProgress = useCallback(
		(position, duration) => {
			const progressPercentage = duration > 0 ? (position / duration) * 100 : 0;

			updateProgress.mutate({
				contentId: videoId,
				progress: progressPercentage,
				metadata: {
					content_type: "video",
					position,
					duration,
				},
			});
		},
		[updateProgress, videoId],
	);

	return {
		progress: {
			percentage: progress.percentage,
			value: progress.percentage,
		},
		isLoading,
		error,
		updateVideoProgress,
		updatePosition: updateVideoProgress, // Use the same memoized function
	};
}
