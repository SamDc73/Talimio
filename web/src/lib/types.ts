type ContentType = "youtube" | "flashcards"

interface ContentItem {
	id: string
	type: ContentType
	title: string
	description: string
	lastAccessedDate: string
	createdDate: string
	progress: number
	tags: string[]
	channelName?: string // Optional for YouTube content
}

interface FilterOption {
	id: string
	label: string
	icon: "Search" | "Youtube" | "Layers" | "BookOpen" | "FileText"
}

interface SortOption {
	id: string
	label: string
	icon: "Clock" | "CalendarDays" | "ArrowUpDown" | "FileText"
}

// Export a value to make this a proper module
export const types = {
	ContentType,
	ContentItem,
	FilterOption,
	SortOption,
} as const

export type { ContentType, ContentItem, FilterOption, SortOption }
