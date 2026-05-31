import { useContentList } from "./use-content-queries"

/**
 * Content Data Hook (using React Query per state-management.md)
 * - Server state managed by React Query
 * - No local state duplication
 * - Automatic caching and background refetching
 */
export function useContentData(filters, _pinning) {
	// Use React Query for server data
	const { data, isLoading, error, refetch, hasMoreContent, loadRemainingContent } = useContentList(filters)

	// Extract data with defaults
	const contentItems = data?.items || []
	const filterOptions = data?.filterOptions || []
	const sortOptions = data?.sortOptions || []

	return {
		contentItems,
		filterOptions,
		sortOptions,
		isLoading,
		error,
		hasMoreContent,
		loadContentData: refetch, // Map to React Query's refetch
		loadRemainingContent,
	}
}
