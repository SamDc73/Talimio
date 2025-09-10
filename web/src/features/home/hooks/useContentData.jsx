import { useCallback, useEffect, useState } from "react"

import { useToast } from "@/hooks/use-toast"
import { processContentData } from "@/lib/api"
import { api } from "@/lib/apiClient"
import { useContentActions, useContentItems } from "@/stores/useContentStore"
export function useContentData(filters, _pinning) {
	// Use store items directly instead of local state for instant updates
	const storeItems = useContentItems()
	const [filterOptions, setFilterOptions] = useState([])
	const [sortOptions, setSortOptions] = useState([])
	const [isLoading, setIsLoading] = useState(true)
	const { toast } = useToast()
	const { setItems } = useContentActions()

	// Load content data function - memoized to prevent infinite loops
	const loadContentData = useCallback(async () => {
		setIsLoading(true)
		try {
			// Include archived content if we're showing archived or all content
			const includeArchived = filters.archiveFilter === "archived" || filters.archiveFilter === "all"
			// Loading content data based on archive filter

			// Fetch data using the correct cookie-based API client
			const response = await api.get(includeArchived ? "/content?include_archived=true" : "/content")

			// Transform the raw API response to match the expected format
			const data = (response.items || []).map((item) => {
				const mappedItem = {
					id: item.id,
					type: item.type === "youtube" ? "video" : item.type, // Map youtube to video
					title: item.title,
					description: item.description,
					lastAccessedDate: item.lastAccessedDate,
					createdDate: item.createdDate,
					progress: item.progress?.percentage || item.progress || 0, // Extract percentage from progress object
					tags: item.tags || [],
					archived: item.archived || false,
					...(item.type === "youtube" && {
						channel: item.channel, // Use the correct field name from backend
						duration: item.length, // Backend sends 'length' for duration
					}),
					...(item.type === "flashcards" && {
						cardCount: item.cardCount,
						dueCount: item.dueCount,
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
				}
				return mappedItem
			})

			// Process the API data

			const { content, filterOptions: options, sortOptions: sortOpts } = processContentData(data)

			// Content processed successfully

			// Transform content with additional fields - tags come from backend
			const transformedContent = content.map((item) => ({
				...item,
				// Tags are already included from backend response
				// For flashcards, map the existing fields
				totalCards: item.cardCount,
				due: item.dueCount || 0,
				overdue: item.overdueCount || 0,
			}))

			// Set content items in store only (we use store items directly now)
			setItems(transformedContent)

			// Set filter options with icon names (not React elements)
			setFilterOptions(options)

			// Set sort options with icon names (not React elements)
			setSortOptions(sortOpts)

			// Don't initialize pins here - it causes re-renders
			// Pins should be initialized elsewhere
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to load content. Please refresh the page.",
				variant: "destructive",
			})
		} finally {
			setIsLoading(false)
		}
	}, [filters.archiveFilter, toast, setItems]) // Include setItems in dependencies

	// Fetch content data on component mount and when archive filter changes
	useEffect(() => {
		loadContentData()
	}, [loadContentData]) // Now properly memoized with correct dependencies

	// Listen for content events - only reload when necessary
	useEffect(() => {
		const handleReload = () => loadContentData()
		// Don't reload for delete/archive - store handles these optimistically
		// Only reload for unarchive since we need to fetch the item data
		const handleContentUnarchived = () => loadContentData()

		window.addEventListener("reloadContent", handleReload)
		window.addEventListener("contentUnarchived", handleContentUnarchived)

		return () => {
			window.removeEventListener("reloadContent", handleReload)
			window.removeEventListener("contentUnarchived", handleContentUnarchived)
		}
	}, [loadContentData])

	return {
		contentItems: storeItems, // Use store items directly for instant updates
		setContentItems: setItems, // Map to store setter for compatibility
		filterOptions,
		setFilterOptions,
		sortOptions,
		setSortOptions,
		isLoading,
		loadContentData,
	}
}
