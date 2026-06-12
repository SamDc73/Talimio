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

const contentStatusByArchiveFilter = {
	active: "active",
	archived: "archived",
	all: "all",
}

const getContentStatus = (archiveFilter) => contentStatusByArchiveFilter[archiveFilter] || "active"

const buildContentListUrl = ({ page, status }) => {
	const params = new URLSearchParams({
		page: String(page),
		pageSize: String(DASHBOARD_CONTENT_PAGE_SIZE),
		status,
	})

	return `/content?${params.toString()}`
}

const fetchContentPage = (contentStatus, page) => {
	return api.get(buildContentListUrl({ page, status: contentStatus }))
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

const updateItemStatus = (old, itemId, status) => {
	if (!old) return old
	return {
		...old,
		items: old.items?.map((item) => (item.id === itemId || item.uuid === itemId ? { ...item, status } : item)),
	}
}

const removeItemAndUpdateTotal = (old, itemId) => {
	if (!old) return old
	const items = old.items?.filter((item) => !(item.id === itemId || item.uuid === itemId))
	return {
		...old,
		items,
		total: typeof old.total === "number" ? Math.max(old.total - 1, 0) : old.total,
	}
}

const updateArchiveStatusInCaches = (queryClient, itemId, status) => {
	queryClient.getQueriesData({ queryKey: contentKeys.all }).forEach(([queryKey, data]) => {
		const filters = queryKey[2]
		const cachedStatus = filters?.status

		if (cachedStatus === "all") {
			queryClient.setQueryData(queryKey, updateItemStatus(data, itemId, status))
			return
		}

		if (cachedStatus === status) {
			queryClient.setQueryData(queryKey, updateItemStatus(data, itemId, status))
			return
		}

		if (cachedStatus === "active" || cachedStatus === "archived") {
			queryClient.setQueryData(queryKey, removeItemAndUpdateTotal(data, itemId))
		}
	})
}

const transformContentItems = (items) =>
	items.map((item) => ({
		id: item.id,
		type: item.type === "youtube" ? "video" : item.type,
		title: item.title,
		description: item.description,
		status: item.status,
		lastAccessedDate: item.updatedAt,
		createdDate: item.createdAt,
		progress: getProgressPercentage(item.progress),
		tags: item.tags || [],
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

/**
 * Fetch content list with proper caching
 */
export function useContentList(filters = {}) {
	const queryClient = useQueryClient()
	const contentStatus = getContentStatus(filters.archiveFilter)
	const queryKey = contentKeys.list({ status: contentStatus })

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
			remainingPageNumbers.map((pageNumber) => fetchContentPage(contentStatus, pageNumber))
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
			const contentPage = await fetchContentPage(contentStatus, 1)
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
				perPage: contentPage.perPage ?? DASHBOARD_CONTENT_PAGE_SIZE,
				filterOptions,
				sortOptions,
			}
		},
		staleTime: 30 * 1000, // Data fresh for 30 seconds
		gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
	})

	return {
		data: query.data,
		error: query.error,
		hasMoreContent: Boolean(query.data?.items && query.data.items.length < query.data.total),
		isLoading: query.isLoading,
		loadRemainingContent,
		refetch: query.refetch,
	}
}

/**
 * Delete content with optimistic update
 */
export function useDeleteContent() {
	const queryClient = useQueryClient()

	return useMutation({
		mutationFn: async ({ itemId, itemType, force = false }) => {
			await deleteContent(itemType, itemId, { force })
			return { itemId, itemType }
		},

		// Optimistic update
		onMutate: async ({ itemId, itemType, force }) => {
			// Cancel any outgoing refetches
			await queryClient.cancelQueries({ queryKey: contentKeys.all })

			// Snapshot the previous value
			const previousContent = queryClient.getQueriesData({
				queryKey: contentKeys.all,
			})

			const canConflict = itemType === "book" && !force
			if (!canConflict) {
				// Optimistically update all content queries
				queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => removeItemFromCache(old, itemId))
			}

			// Return snapshot for rollback
			return { previousContent, removedOptimistically: !canConflict }
		},

		onSuccess: ({ itemId }, _variables, context) => {
			if (!context?.removedOptimistically) {
				queryClient.setQueriesData({ queryKey: contentKeys.all }, (old) => removeItemFromCache(old, itemId))
			}
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

			const status = archive ? "archived" : "active"

			updateArchiveStatusInCaches(queryClient, item.id, status)

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

		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: contentKeys.all })
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
