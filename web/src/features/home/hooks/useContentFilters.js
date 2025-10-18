import { useState } from "react"

export const useContentFilters = () => {
	const [searchQuery, setSearchQuery] = useState("")
	const [isGenerateMode, setIsGenerateMode] = useState(false)
	const [isYoutubeMode, setIsYoutubeMode] = useState(false)
	const [activeFilter, setActiveFilter] = useState("all")
	const [activeSort, setActiveSort] = useState("last-accessed")
	const [sortDirection, setSortDirection] = useState("desc")
	const [archiveFilter, setArchiveFilter] = useState("active")
	const [tagFilter, setTagFilter] = useState("")
	const [showAll, setShowAll] = useState(false)

	const toggleSortDirection = () => {
		setSortDirection(sortDirection === "asc" ? "desc" : "asc")
	}

	const resetAllFilters = () => {
		setActiveFilter("all")
		setActiveSort("last-accessed")
		setSortDirection("desc")
		setTagFilter("")
	}

	const getFilteredAndSortedContent = (contentItems) => {
		return (Array.isArray(contentItems) ? contentItems : [])
			.filter((item) => {
				// Apply content type filter
				if (activeFilter === "all") return true
				if (activeFilter === "course") return item.type === "course"
				return item.type === activeFilter
			})
			.filter((item) => {
				// Apply archive filter
				const isArchived = Boolean(item.archived)
				if (archiveFilter === "active") return !isArchived
				if (archiveFilter === "archived") return isArchived
				return true // "all" shows both archived and active
			})
			.filter((item) => {
				if (!searchQuery) return true

				const query = searchQuery.toLowerCase()
				const title = item.title.toLowerCase()
				const tags = item.tags ? item.tags.some((tag) => tag.toLowerCase().includes(query)) : false

				if (item.type === "course") {
					return title.includes(query) || item.description.toLowerCase().includes(query) || tags
				}
				if (item.type === "book") {
					return title.includes(query) || item.author?.toLowerCase().includes(query) || tags
				}
				if (item.type === "youtube") {
					const channelName = item.channelName || item.channel || ""
					return title.includes(query) || channelName?.toLowerCase().includes(query) || tags
				}
				return true
			})
			.filter((item) => {
				// Apply tag filter
				if (!tagFilter) return true

				return item.tags?.some((tag) => tag.toLowerCase().includes(tagFilter.toLowerCase()))
			})
			.sort((a, b) => {
				const direction = sortDirection === "asc" ? 1 : -1

				switch (activeSort) {
					case "last-accessed":
						return direction * (new Date(a.lastAccessedDate).getTime() - new Date(b.lastAccessedDate).getTime())
					case "created":
						return direction * (new Date(a.createdDate).getTime() - new Date(b.createdDate).getTime())
					case "progress":
						return direction * (a.progress - b.progress)
					case "title":
						return direction * a.title.localeCompare(b.title)
					default:
						return 0
				}
			})
	}

	return {
		// Search and mode states
		searchQuery,
		setSearchQuery,
		isGenerateMode,
		setIsGenerateMode,
		isYoutubeMode,
		setIsYoutubeMode,

		// Filter states
		activeFilter,
		setActiveFilter,
		activeSort,
		setActiveSort,
		sortDirection,
		setSortDirection,
		archiveFilter,
		setArchiveFilter,
		tagFilter,
		setTagFilter,
		showAll,
		setShowAll,

		// Filter functions
		toggleSortDirection,
		resetAllFilters,
		getFilteredAndSortedContent,
	}
}
