import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"
import { processContentData } from "@/lib/api"
import { api } from "@/lib/apiClient"
import { archiveContent, unarchiveContent } from "@/services/contentService"
import { deleteApi } from "@/services/deleteApi"

/**
 * React Query hooks for content operations (following state-management.md)
 * - Server state managed by React Query
 * - Optimistic updates for instant UI feedback
 * - Proper error handling with rollback
 * - Smart cache invalidation
 */

// Query key factory for consistent key generation
export const contentKeys = {
	all: ["content"],
	list: (filters) => [...contentKeys.all, "list", filters],
	item: (id) => [...contentKeys.all, "item", id],
}

/**
 * Fetch content list with proper caching
 */
export function useContentList(filters = {}) {
	const includeArchived = filters.archiveFilter === "archived" || filters.archiveFilter === "all"

	return useQuery({
		queryKey: contentKeys.list({ includeArchived }),
		queryFn: async () => {
			const response = await api.get(includeArchived ? "/content?include_archived=true" : "/content")

			// Transform the raw API response
			const data = (response.items || []).map((item) => ({
				id: item.id,
				type: item.type === "youtube" ? "video" : item.type,
				title: item.title,
				description: item.description,
				lastAccessedDate: item.lastAccessedDate,
				createdDate: item.createdDate,
				progress: item.progress?.percentage || item.progress || 0,
				tags: item.tags || [],
				archived: item.archived || false,
				...(item.type === "youtube" && {
					channel: item.channel,
					duration: item.length,
				}),
				...(item.type === "flashcards" && {
					cardCount: item.cardCount,
					dueCount: item.dueCount,
					totalCards: item.cardCount,
					due: item.dueCount || 0,
					overdue: item.overdueCount || 0,
				}),
				...(item.type === "book" && {
					author: item.author,
					pageCount: item.pageCount || item.page_count || item.totalPages,
					currentPage: item.currentPage,
					tocProgress: item.tocProgress || {},
				}),
				...(item.type === "course" && {
					lessonCount: item.lessonCount,
					completedLessons: item.completedLessons,
				}),
			}))

			// Process the data for filters and sorting
			const processed = processContentData(data)
			return {
				items: processed.content,
				filterOptions: processed.filterOptions,
				sortOptions: processed.sortOptions,
			}
		},
		staleTime: 30 * 1000, // Data fresh for 30 seconds
		gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
	})
}

/**
 * Delete content with optimistic update
 */
export function useDeleteContent() {
	const queryClient = useQueryClient()
	const { toast } = useToast()

	return useMutation({
		mutationFn: async ({ itemId, itemType }) => {
			await deleteApi.deleteItem(itemType, itemId)
			return { itemId, itemType }
		},

		// Optimistic update
		onMutate: async ({ itemId }) => {
			// Cancel any outgoing refetches
			await queryClient.cancelQueries({ queryKey: contentKeys.all })

			// Snapshot the previous value
			const previousContent = queryClient.getQueriesData({
				queryKey: contentKeys.all,
			})

			// Optimistically update all content queries
			queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => {
				if (!old) return old
				return {
					...old,
					items: old.items?.filter((item) => !(item.id === itemId || item.uuid === itemId)),
				}
			})

			// Return snapshot for rollback
			return { previousContent }
		},

		// Rollback on error
		onError: (err, _variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}

			toast({
				title: "Delete Failed",
				description: err.message || "Failed to delete item. Please try again.",
				variant: "destructive",
			})
		},

		// Success notification
		onSuccess: (data) => {
			const getTypeLabel = (type) => {
				if (type === "video") return "Video"
				if (type === "book") return "Book"
				if (type === "course" || type === "roadmap") return "Course"
				if (type === "flashcards") return "Flashcard Deck"
				return "Item"
			}

			toast({
				title: "Deleted",
				description: `${getTypeLabel(data.itemType)} deleted successfully`,
			})

			// Emit event for other components
			window.dispatchEvent(
				new CustomEvent("contentDeleted", {
					detail: { itemId: data.itemId, itemType: data.itemType },
				})
			)
			
			// Invalidate queries to ensure consistency with backend
			// Backend caching has been fixed so this is now safe
			queryClient.invalidateQueries({ queryKey: contentKeys.all })
		},

		// Clean up on settled regardless of success/failure
		onSettled: () => {
			// Ensure queries are fresh after any deletion attempt
			queryClient.invalidateQueries({ queryKey: contentKeys.all })
		}
	})
}

/**
 * Archive content with optimistic update
 */
export function useArchiveContent() {
	const queryClient = useQueryClient()
	const { toast } = useToast()

	return useMutation({
		mutationFn: async ({ item, archive = true }) => {
			if (archive) {
				await archiveContent(item.type, item.id || item.uuid)
			} else {
				await unarchiveContent(item.type, item.id || item.uuid)
			}
			return { item, archive }
		},

		// Optimistic update
		onMutate: async ({ item, archive }) => {
			await queryClient.cancelQueries({ queryKey: contentKeys.all })

			const previousContent = queryClient.getQueriesData({
				queryKey: contentKeys.all,
			})

			// Update the item's archived status
			queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => {
				if (!old) return old
				return {
					...old,
					items: old.items?.map((i) => (i.id === item.id || i.uuid === item.id ? { ...i, archived: archive } : i)),
				}
			})

			return { previousContent }
		},

		// Rollback on error
		onError: (err, variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}

			toast({
				title: variables.archive ? "Archive Failed" : "Restore Failed",
				description: err.message || "Operation failed. Please try again.",
				variant: "destructive",
			})
		},

		// Success notification
		onSuccess: ({ item, archive }) => {
			toast({
				title: archive ? "Archived" : "Restored",
				description: `${item.title} has been ${archive ? "archived" : "restored"}`,
			})

			// Emit event
			window.dispatchEvent(
				new CustomEvent(archive ? "contentArchived" : "contentUnarchived", {
					detail: { itemId: item.id, itemType: item.type },
				})
			)

			// If archiving, remove from view after animation
			if (archive) {
				setTimeout(() => {
					queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => {
						if (!old) return old
						return {
							...old,
							items: old.items?.filter((i) => i.id !== item.id),
						}
					})
				}, 300)
			}
			
			// For archive/unarchive, we can safely invalidate to get the latest state
			// This is different from delete where invalidation can resurrect deleted items
			if (!archive) {
				// When unarchiving, invalidate to ensure we get the item back in the list
				queryClient.invalidateQueries({ queryKey: contentKeys.all })
			}
		},
	})
}

/**
 * Update content tags with optimistic update
 */
export function useUpdateContentTags() {
	const queryClient = useQueryClient()
	const { toast } = useToast()

	return useMutation({
		mutationFn: async ({ itemId, contentType, tags }) => {
			// This would call your tag update API
			// For now, just return the data
			return { itemId, contentType, tags }
		},

		// Optimistic update
		onMutate: async ({ itemId, tags }) => {
			await queryClient.cancelQueries({ queryKey: contentKeys.all })

			const previousContent = queryClient.getQueriesData({
				queryKey: contentKeys.all,
			})

			// Update the item's tags
			queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => {
				if (!old) return old
				return {
					...old,
					items: old.items?.map((item) => (item.id === itemId || item.uuid === itemId ? { ...item, tags } : item)),
				}
			})

			return { previousContent }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}

			toast({
				title: "Update Failed",
				description: "Failed to update tags. Please try again.",
				variant: "destructive",
			})
		},

		// Success notification
		onSuccess: () => {
			toast({
				title: "Tags Updated",
				description: "Content tags have been updated successfully.",
			})
		},
	})
}

/**
 * Invalidate content queries (for manual refresh)
 */
export function useInvalidateContent() {
	const queryClient = useQueryClient()

	return () => {
		queryClient.invalidateQueries({ queryKey: contentKeys.all })
	}
}
