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
