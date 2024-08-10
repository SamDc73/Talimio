export interface ContentItem {
	id: string
	type: "youtube" | "flashcards" | "book" | "roadmap" | "course"
	title: string
	description: string
	lastAccessedDate: string
	createdDate: string
	progress: number
	tags: string[]
	archived?: boolean
	// YouTube specific
	channelName?: string
	channel_name?: string
	duration?: number
	// Flashcards specific
	cardCount?: number
	dueCount?: number
	// Book specific
	author?: string
	pageCount?: number
	pages?: number
	currentPage?: number
	// Roadmap specific
	nodeCount?: number
	completedNodes?: number
	// Course specific
	modules?: number
}

export interface FilterOption {
	id: string
	label: string
	icon: "Search" | "Youtube" | "Layers" | "BookOpen" | "FileText"
}

export interface SortOption {
	id: string
	label: string
	icon: "Clock" | "CalendarDays" | "ArrowUpDown" | "FileText"
}

export async function fetchContentData(includeArchived = false): Promise<ContentItem[]> {
	try {
		const url = new URL("http://localhost:8080/api/v1/content")
		if (includeArchived) {
			url.searchParams.append("include_archived", "true")
		}

		const response = await fetch(url.toString(), {
			headers: {
				Accept: "application/json",
			},
		})

		if (!response.ok) {
			throw new Error(`HTTP error! status: ${response.status}`)
		}

		const data = await response.json()
		if (import.meta.env.VITE_DEBUG_MODE === "true") {
		}

		// Map the API response to the expected ContentItem format
		return data.items.map((item: Record<string, unknown>) => {
			const mappedItem = {
				id: item.id as string,
				type: item.type as ContentItem["type"],
				title: item.title as string,
				description: item.description as string,
				lastAccessedDate: item.lastAccessedDate as string,
				createdDate: item.createdDate as string,
				progress: (item.progress as number) || 0,
				tags: (item.tags as string[]) || [],
				archived: (item.archived as boolean) || false,
				// Map specific fields based on content type
				...(item.type === "youtube" && {
					channelName: (item.channelName as string) || (item.channel_name as string),
					channel_name: (item.channelName as string) || (item.channel_name as string),
					duration: item.duration as number,
				}),
				...(item.type === "flashcards" && {
					cardCount: item.cardCount as number,
					dueCount: item.dueCount as number,
				}),
				...(item.type === "book" && {
					author: item.author as string,
					pageCount: (item.pageCount as number) || (item.page_count as number),
					pages: (item.pageCount as number) || (item.page_count as number),
					currentPage: (item.currentPage as number) || (item.current_page as number),
				}),
				...(item.type === "roadmap" && {
					nodeCount: item.nodeCount as number,
					completedNodes: item.completedNodes as number,
				}),
				...(item.type === "course" && {
					modules: item.modules as number,
				}),
			}
			return mappedItem
		})
	} catch (_error) {
		return []
	}
}

export function processContentData(data: ContentItem[]) {
	// Generate filter options based on content types
	const filterOptions: FilterOption[] = [
		{ id: "all", label: "All Content", icon: "Search" },
		{ id: "course", label: "Courses", icon: "BookOpen" },
		{ id: "youtube", label: "Videos", icon: "Youtube" },
		{ id: "flashcards", label: "Flashcards", icon: "Layers" },
		{ id: "book", label: "Books", icon: "FileText" },
	]

	// Define sort options
	const sortOptions: SortOption[] = [
		{ id: "last-accessed", label: "Last Opened", icon: "Clock" },
		{ id: "created", label: "Date Created", icon: "CalendarDays" },
		{ id: "progress", label: "Progress", icon: "ArrowUpDown" },
		{ id: "title", label: "Title", icon: "FileText" },
	]

	return {
		content: data,
		filterOptions,
		sortOptions,
	}
}
