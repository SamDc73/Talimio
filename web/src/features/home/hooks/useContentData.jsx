import { useEffect } from "react"
import { useContentList, useInvalidateContent } from "@/hooks/useContentQueries"

/**
 * Content Data Hook (using React Query per state-management.md)
 * - Server state managed by React Query
 * - No local state duplication
 * - Automatic caching and background refetching
 */
export function useContentData(filters, _pinning) {
	// Use React Query for server data
	const { data, isLoading, error, refetch } = useContentList(filters)

	// Get invalidate function for manual refresh
	const invalidateContent = useInvalidateContent()

	// Extract data with defaults
	const contentItems = data?.items || []
	const filterOptions = data?.filterOptions || []
	const sortOptions = data?.sortOptions || []

	// Listen for events that require refresh
	useEffect(() => {
		const handleContentUnarchived = () => {
			// Invalidate queries to refetch
			invalidateContent()
		}

		// Only listen for unarchive (delete/archive handled by mutations)
		window.addEventListener("contentUnarchived", handleContentUnarchived)

		return () => {
			window.removeEventListener("contentUnarchived", handleContentUnarchived)
		}
	}, [invalidateContent])

	return {
		contentItems,
		setContentItems: () => {},
		filterOptions,
		setFilterOptions: () => {},
		sortOptions,
		setSortOptions: () => {},
		isLoading,
		error,
		loadContentData: refetch, // Map to React Query's refetch
	}
}
