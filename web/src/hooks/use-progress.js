import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/apiClient"
import { contentKeys, contentQueryHasItem, patchContentItemInCache } from "@/lib/content-query-cache"

const progressKey = (contentId) => ["progress", contentId]
const EMPTY_METADATA = Object.freeze({})

/**
 * Fetch progress for one content item.
 */
async function fetchProgress(contentId) {
	if (!contentId) {
		return null
	}

	return await api.get(`/progress/${contentId}`)
}

/**
 * Hook for fetching one item's progress.
 */
export function useSingleProgress(contentId) {
	const query = useQuery({
		queryKey: progressKey(contentId),
		queryFn: () => fetchProgress(contentId),
		staleTime: 30 * 1000, // 30 seconds
		gcTime: 10 * 60 * 1000, // 10 minutes
		refetchOnWindowFocus: false, // Disable aggressive refetching
		refetchInterval: false, // No automatic polling (use manual invalidation)
		enabled: Boolean(contentId),
		// Error recovery with retry
		retry: 3,
		retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30_000),
	})

	const progressData = query.data || null

	return {
		// Only include stable properties from query
		isLoading: query.isLoading,
		error: query.error,
		isError: query.isError,
		isSuccess: query.isSuccess,
		refetch: query.refetch,
		// Custom data properties
		data: progressData?.progress_percentage ?? 0,
		fullData: progressData,
		metadata: progressData?.metadata ?? EMPTY_METADATA,
	}
}

/**
 * Hook for updating progress with optimistic updates
 */
export function useUpdateProgress() {
	const queryClient = useQueryClient()

	return useMutation({
		mutationFn: ({ contentId, progress, metadata }) =>
			api.put(`/progress/${contentId}`, {
				progress_percentage: progress,
				metadata,
			}),
		onMutate: async ({ contentId, progress, metadata }) => {
			// Cancel any outgoing refetches
			await queryClient.cancelQueries({ queryKey: progressKey(contentId), exact: true })
			await queryClient.cancelQueries({ queryKey: contentKeys.all })

			// Snapshot matching caches for rollback
			const previousProgress = queryClient.getQueryData(progressKey(contentId))
			const previousContentQueries = queryClient.getQueriesData({ queryKey: contentKeys.all })

			// Optimistically update this progress query.
			queryClient.setQueryData(progressKey(contentId), (old) => {
				if (old && typeof old === "object") {
					return {
						...old,
						progress_percentage: progress,
						metadata: metadata || {},
					}
				}

				return {
					progress_percentage: progress,
					metadata: metadata || {},
				}
			})

			patchContentItemInCache(queryClient, contentId, (item) => ({ ...item, progress }))

			// Return context with snapshot
			return { previousProgress, previousContentQueries, contentId }
		},
		onError: (_err, _variables, context) => {
			// Rollback on error
			if (context?.contentId) {
				if (context.previousProgress === undefined) {
					queryClient.removeQueries({ queryKey: progressKey(context.contentId), exact: true })
				} else {
					queryClient.setQueryData(progressKey(context.contentId), context.previousProgress)
				}
			}
			if (context?.previousContentQueries) {
				context.previousContentQueries.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}
		},
		onSettled: (_data, _error, variables) => {
			if (!variables?.contentId) {
				return
			}

			queryClient.invalidateQueries({
				queryKey: progressKey(variables.contentId),
				exact: true,
			})
			queryClient.invalidateQueries({
				queryKey: contentKeys.all,
				predicate: (query) => contentQueryHasItem(query.state.data, variables.contentId),
			})
		},
	})
}
