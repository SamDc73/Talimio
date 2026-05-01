import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { archiveContent, deleteContent, unarchiveContent } from "@/api/contentApi"
import { api } from "@/lib/apiClient"
import { contentKeys, patchContentItemInCache } from "@/lib/content-query-cache"

/**
 * React Query hooks for content operations (following state-management.md)
 * - Server state managed by React Query
 * - Optimistic updates for instant UI feedback
 * - Proper error handling with rollback
 * - Smart cache invalidation
 */

const DASHBOARD_CONTENT_PAGE_SIZE = 100

const buildContentListUrl = ({ includeArchived, page }) => {
	const params = new URLSearchParams({
		page: String(page),
		page_size: String(DASHBOARD_CONTENT_PAGE_SIZE),
	})

	if (includeArchived) {
		params.set("include_archived", "true")
	}

	return `/content?${params.toString()}`
}

const fetchContentPage = (includeArchived, page) => {
	return api.get(buildContentListUrl({ includeArchived, page }))
}

const getProgressPercentage = (progress) => {
	if (typeof progress === "number") {
		return progress
	}
	if (progress && typeof progress === "object" && typeof progress.percentage === "number") {
		return progress.percentage
	}
	return 0
}

const removeItemFromCache = (old, itemId) => {
	if (!old) return old
	return {
		...old,
		items: old.items?.filter((item) => !(item.id === itemId || item.uuid === itemId)),
	}
}

const updateItemArchiveStatus = (old, itemId, archive) => {
	if (!old) return old
	return {
		...old,
		items: old.items?.map((item) =>
			item.id === itemId || item.uuid === itemId ? { ...item, archived: archive } : item
		),
	}
}

const scheduleArchiveRemoval = (queryClient, itemId) => {
	setTimeout(() => {
		queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => removeItemFromCache(old, itemId))
	}, 300)
}

/**
 * Fetch content list with proper caching
 */
export function useContentList(filters = {}) {
	const queryClient = useQueryClient()
	const includeArchived = filters.archiveFilter === "archived" || filters.archiveFilter === "all"
	const queryKey = contentKeys.list({ includeArchived })

	const transformContentItems = (items) =>
		items.map((item) => ({
			id: item.id,
			type: item.type === "youtube" ? "video" : item.type,
			title: item.title,
			description: item.description,
			lastAccessedDate: item.lastAccessedDate,
			createdDate: item.createdDate,
			progress: getProgressPercentage(item.progress),
			tags: item.tags || [],
			archived: item.archived || false,
			...(item.type === "youtube" && {
				channel: item.channel,
				duration: item.length,
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

	const loadRemainingContent = async () => {
		const currentData = queryClient.getQueryData(queryKey)
		if (!currentData?.items?.length || currentData.items.length >= currentData.total) {
			return
		}

		const perPage = currentData.perPage || DASHBOARD_CONTENT_PAGE_SIZE
		const loadedPages = Math.ceil(currentData.items.length / perPage)
		const totalPages = Math.ceil(currentData.total / perPage)
		const remainingPageNumbers = Array.from({ length: totalPages - loadedPages }, (_, index) => loadedPages + index + 1)
		const remainingPages = await Promise.all(
			remainingPageNumbers.map((pageNumber) => fetchContentPage(includeArchived, pageNumber))
		)
		const remainingItems = transformContentItems(remainingPages.flatMap((pageData) => pageData.items || []))

		queryClient.setQueryData(queryKey, {
			...currentData,
			items: [...currentData.items, ...remainingItems],
			page: totalPages,
		})
	}

	const query = useQuery({
		queryKey,
		queryFn: async () => {
			const contentPage = await fetchContentPage(includeArchived, 1)
			const responseItems = contentPage.items || []

			const data = transformContentItems(responseItems)

			// Return processed data with filter and sort options
			const filterOptions = [
				{ id: "all", label: "All Content", icon: "Search" },
				{ id: "course", label: "Courses", icon: "BookOpen" },
				{ id: "video", label: "Videos", icon: "Youtube" },
				{ id: "book", label: "Books", icon: "FileText" },
			]

			const sortOptions = [
				{ id: "last-accessed", label: "Last Opened", icon: "Clock" },
				{ id: "created", label: "Date Created", icon: "CalendarDays" },
				{ id: "progress", label: "Progress", icon: "ArrowUpDown" },
				{ id: "title", label: "Title", icon: "FileText" },
			]

			return {
				items: data,
				total: contentPage.total ?? data.length,
				page: contentPage.page ?? 1,
				perPage: contentPage.perPage ?? contentPage.per_page ?? DASHBOARD_CONTENT_PAGE_SIZE,
				filterOptions,
				sortOptions,
			}
		},
		staleTime: 30 * 1000, // Data fresh for 30 seconds
		gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
	})

	return {
		...query,
		hasMoreContent: Boolean(query.data?.items && query.data.items.length < query.data.total),
		loadRemainingContent,
	}
}

/**
 * Delete content with optimistic update
 */
export function useDeleteContent() {
	const queryClient = useQueryClient()

	return useMutation({
		mutationFn: async ({ itemId, itemType }) => {
			await deleteContent(itemType, itemId)
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
			queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => removeItemFromCache(old, itemId))

			// Return snapshot for rollback
			return { previousContent }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}
		},

		// Clean up on settled regardless of success/failure
		onSettled: () => {
			// Ensure queries are fresh after any deletion attempt
			queryClient.invalidateQueries({ queryKey: contentKeys.all })
		},
	})
}

/**
 * Archive content with optimistic update
 */
export function useArchiveContent() {
	const queryClient = useQueryClient()

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
			queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => updateItemArchiveStatus(old, item.id, archive))

			return { previousContent }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}
		},

		// Success notification
		onSuccess: ({ item, archive }) => {
			// Emit event
			window.dispatchEvent(
				new CustomEvent(archive ? "contentArchived" : "contentUnarchived", {
					detail: { itemId: item.id, itemType: item.type },
				})
			)

			// If archiving, remove from view after animation
			if (archive) {
				scheduleArchiveRemoval(queryClient, item.id)
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
			patchContentItemInCache(queryClient, itemId, (item) => ({ ...item, tags }))

			return { previousContent }
		},

		// Rollback on error
		onError: (_err, _variables, context) => {
			if (context?.previousContent) {
				context.previousContent.forEach(([queryKey, data]) => {
					queryClient.setQueryData(queryKey, data)
				})
			}
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
