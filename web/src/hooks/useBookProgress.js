import { useCallback, useMemo, useRef } from "react";
import { useProgress, useUpdateProgress } from "./useProgress";

/**
 * Adapter hook for backward compatibility with book progress
 * Maps the new unified progress API to the old book-specific interface
 */
export function useBookProgress(bookId) {
	// Memoize the contentIds array to prevent unnecessary re-queries
	const contentIds = useMemo(() => (bookId ? [bookId] : []), [bookId]);

	const progressQuery = useProgress(contentIds);
	const updateProgress = useUpdateProgress();

	// Use refs to store functions that don't need to trigger re-renders
	const refetchRef = useRef(progressQuery.refetch);
	refetchRef.current = progressQuery.refetch;

	// Get the current progress data from the map
	const currentProgress = progressQuery.data?.[bookId] || 0;
	const rawMetadata = progressQuery.metadata?.[bookId] || {};

	// Extract values with defaults
	const tocProgress =
		rawMetadata.toc_progress || rawMetadata.completedChapters || {};
	const currentPage = rawMetadata.current_page || 0;
	const totalPages = rawMetadata.total_pages || 0;
	const zoomLevel = rawMetadata.zoom_level || 100;

	// Simple return object - no complex memoization needed
	// The component using this hook should handle memoization if needed
	// Helper to calculate progress from TOC (only counts leaf chapters)
	const calculateProgressFromToc = useCallback((tocProgress, totalChapters) => {
		if (!totalChapters || totalChapters === 0) return 0;

		// Backend expects boolean values, count only true values
		const completedCount = Object.values(tocProgress).filter(
			(status) => status === true,
		).length;

		return Math.round((completedCount / totalChapters) * 100);
	}, []);

	return {
		progress: {
			percentage: currentProgress,
			value: currentProgress, // Alias for compatibility
		},
		metadata: {
			currentPage,
			totalPages,
			zoomLevel,
			tocProgress,
		},
		isLoading: progressQuery.isLoading,
		loading: progressQuery.isLoading, // Legacy alias
		error: progressQuery.error,
		refetch: () => refetchRef.current(),
		isCompleted: (chapterId) => {
			const status = tocProgress[chapterId];
			return status === true || status === "completed";
		},
		toggleCompletion: async (chapterId, totalChaptersOverride) => {
			const currentStatus = tocProgress[chapterId];
			// Backend expects boolean values
			const newStatus = !(
				currentStatus === true || currentStatus === "completed"
			);

			const newTocProgress = {
				...tocProgress,
				[chapterId]: newStatus,
			};

			// Calculate new progress based on completed chapters
			const totalChapters =
				totalChaptersOverride ||
				rawMetadata.totalChapters ||
				Object.keys(newTocProgress).length;
			const newProgress = calculateProgressFromToc(
				newTocProgress,
				totalChapters,
			);

			await updateProgress.mutateAsync({
				contentId: bookId,
				progress: newProgress,
				metadata: {
					content_type: "book",
					toc_progress: newTocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					totalChapters: totalChapters,
				},
			});
		},
		batchUpdate: async (updates, totalChaptersOverride) => {
			const newTocProgress = { ...tocProgress };

			updates.forEach(({ itemId, completed }) => {
				// Backend expects boolean values
				newTocProgress[itemId] = completed;
			});

			// Calculate new progress based on completed chapters
			const totalChapters =
				totalChaptersOverride ||
				rawMetadata.totalChapters ||
				Object.keys(newTocProgress).length;
			const newProgress = calculateProgressFromToc(
				newTocProgress,
				totalChapters,
			);

			await updateProgress.mutateAsync({
				contentId: bookId,
				progress: newProgress,
				metadata: {
					content_type: "book",
					toc_progress: newTocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					totalChapters: totalChapters,
				},
			});
		},
		updateProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: bookId,
				progress,
				metadata: {
					content_type: "book",
					toc_progress: tocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					...metadata,
				},
			}),
		// Legacy method names for compatibility
		setProgress: (progress, metadata = {}) =>
			updateProgress.mutate({
				contentId: bookId,
				progress,
				metadata: {
					content_type: "book",
					toc_progress: tocProgress,
					current_page: currentPage,
					total_pages: totalPages,
					zoom_level: zoomLevel,
					...metadata,
				},
			}),
	};
}

/**
 * Hook for updating book-specific metadata along with progress
 */
export function useBookProgressWithMetadata(bookId) {
	const updateProgress = useUpdateProgress();
	const { progress, isLoading, error } = useBookProgress(bookId);

	const updateBookProgress = useCallback(
		(currentPage, totalPages) => {
			const progressPercentage =
				totalPages > 0 ? (currentPage / totalPages) * 100 : 0;

			updateProgress.mutate({
				contentId: bookId,
				progress: progressPercentage,
				metadata: {
					content_type: "book",
					current_page: currentPage,
					total_pages: totalPages,
				},
			});
		},
		[bookId, updateProgress],
	);

	const updatePage = useCallback(
		(page, totalPages) => updateBookProgress(page, totalPages),
		[updateBookProgress],
	);

	// Memoize the progress object to ensure stable reference
	const progressObject = useMemo(
		() => ({
			percentage: progress.percentage,
			value: progress.percentage,
		}),
		[progress.percentage],
	);

	return useMemo(
		() => ({
			progress: progressObject,
			isLoading,
			error,
			updateBookProgress,
			updatePage,
		}),
		[progressObject, isLoading, error, updateBookProgress, updatePage],
	);
}
