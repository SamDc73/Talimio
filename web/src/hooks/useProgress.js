import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/apiClient";

// Maximum batch size for progress fetching
const MAX_BATCH_SIZE = 100;

// Helper to get local progress from localStorage
function getLocalProgress(ids) {
	try {
		const stored = localStorage.getItem("progress-fallback");
		if (stored) {
			const allProgress = JSON.parse(stored);
			return ids.reduce((acc, id) => {
				if (allProgress[id] !== undefined) {
					acc[id] = allProgress[id];
				}
				return acc;
			}, {});
		}
	} catch (error) {
		console.error("Failed to read local progress:", error);
	}
	return {};
}

// Helper to save progress to localStorage
function saveLocalProgress(contentId, progress) {
	try {
		const stored = localStorage.getItem("progress-fallback") || "{}";
		const allProgress = JSON.parse(stored);
		allProgress[contentId] = progress;
		localStorage.setItem("progress-fallback", JSON.stringify(allProgress));
	} catch (error) {
		console.error("Failed to save local progress:", error);
	}
}

/**
 * Batch progress fetching with size limits
 */
async function fetchBatchProgress(contentIds) {
	if (!contentIds || contentIds.length === 0) {
		return {};
	}

	if (contentIds.length <= MAX_BATCH_SIZE) {
		const response = await api.post("/progress/batch", {
			content_ids: contentIds,
		});
		// The API returns { progress: { contentId: { progress_percentage, metadata } } }
		return response?.progress || {};
	}

	// Split into multiple requests for large batches
	const chunks = [];
	for (let i = 0; i < contentIds.length; i += MAX_BATCH_SIZE) {
		chunks.push(contentIds.slice(i, i + MAX_BATCH_SIZE));
	}

	const results = await Promise.all(
		chunks.map(async (chunk) => {
			const response = await api.post("/progress/batch", {
				content_ids: chunk,
			});
			return response?.progress || {};
		}),
	);

	// Merge results using for loop for better performance
	const merged = {};
	for (const data of results) {
		for (const [key, value] of Object.entries(data)) {
			merged[key] = value;
		}
	}
	return merged;
}

/**
 * Hook for fetching progress for multiple content items
 */
export function useProgress(contentIds) {
	const query = useQuery({
		queryKey: ["progress", contentIds],
		queryFn: () => fetchBatchProgress(contentIds),
		staleTime: 30 * 1000, // 30 seconds
		cacheTime: 10 * 60 * 1000, // 10 minutes
		refetchOnWindowFocus: false, // Disable aggressive refetching
		refetchInterval: false, // No automatic polling (use manual invalidation)
		enabled: contentIds && contentIds.length > 0, // Don't query with empty array
		// Error recovery with retry
		retry: 3,
		retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
		onError: (error) => {
			// Log to monitoring
			console.error("Progress fetch failed:", error);
			// Return last known progress from localStorage
			return getLocalProgress(contentIds);
		},
	});

	// Use React.useMemo to ensure stable references
	const { progressMap, metadataMap, fullData } = React.useMemo(() => {
		const data = query.data || {};
		const pMap = {};
		const mMap = {};

		Object.entries(data).forEach(([contentId, progressData]) => {
			// Handle both old format (just percentage) and new format (object with percentage and metadata)
			if (typeof progressData === "number") {
				pMap[contentId] = progressData;
				mMap[contentId] = {};
			} else if (progressData && typeof progressData === "object") {
				pMap[contentId] = progressData.progress_percentage || 0;
				mMap[contentId] = progressData.metadata || {};
			}
		});

		return { progressMap: pMap, metadataMap: mMap, fullData: data };
	}, [query.data]);

	return React.useMemo(
		() => ({
			// Only include stable properties from query
			isLoading: query.isLoading,
			error: query.error,
			isError: query.isError,
			isSuccess: query.isSuccess,
			refetch: query.refetch,
			// Custom data properties
			data: progressMap, // Simple percentage map for backward compatibility
			fullData, // Full data with metadata
			metadata: metadataMap, // Metadata map
		}),
		[
			query.isLoading,
			query.error,
			query.isError,
			query.isSuccess,
			query.refetch,
			progressMap,
			metadataMap,
			fullData,
		],
	);
}

/**
 * Hook for updating progress with optimistic updates
 */
export function useUpdateProgress() {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: ({ contentId, progress, metadata }) =>
			api.put(`/progress/${contentId}`, {
				progress_percentage: progress,
				metadata,
			}),
		onMutate: async ({ contentId, progress, metadata }) => {
			// Cancel any outgoing refetches
			await queryClient.cancelQueries({ queryKey: ["progress"] });

			// Snapshot the previous value
			const previousProgress = queryClient.getQueryData(["progress"]);

			// Optimistically update all queries containing this contentId
			queryClient.setQueriesData(
				{ queryKey: ["progress"], exact: false },
				(old) => {
					if (!old) return old;

					// Create the new progress data with metadata
					const newProgressData = {
						progress_percentage: progress,
						metadata: metadata || {},
					};

					return {
						...old,
						[contentId]: newProgressData,
					};
				},
			);

			// Dispatch event for cross-component sync
			window.dispatchEvent(
				new CustomEvent("progressUpdated", {
					detail: { contentId, progress, metadata },
				}),
			);

			// Save to localStorage for offline fallback
			saveLocalProgress(contentId, { progress_percentage: progress, metadata });

			// Return context with snapshot
			return { previousProgress, contentId };
		},
		onError: (_err, _variables, context) => {
			// Rollback on error
			if (context?.previousProgress) {
				queryClient.setQueriesData(
					{ queryKey: ["progress"], exact: false },
					context.previousProgress,
				);
			}
			toast({
				title: "Error",
				description: "Failed to update progress. Please try again.",
				variant: "destructive",
			});
		},
		onSettled: (_data, _error, variables) => {
			// Always refetch after mutation
			queryClient.invalidateQueries({
				queryKey: ["progress"],
				refetchType: "all", // Force immediate refetch regardless of staleTime
				predicate: (query) => {
					// Only invalidate queries that include this contentId
					const ids = query.queryKey[1];
					return Array.isArray(ids) && ids.includes(variables.contentId);
				},
			});
		},
	});
}

/**
 * Hook for fetching a single item's progress
 */
export function useSingleProgress(contentId) {
	const { data, ...rest } = useProgress(contentId ? [contentId] : []);
	return {
		data: data?.[contentId] || 0,
		...rest,
	};
}
