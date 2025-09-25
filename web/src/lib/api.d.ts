export type ContentType = "youtube"

export interface ContentItem {
	id: string
	type: ContentType
	title: string
	description: string
	lastAccessedDate: string
	createdDate: string
	progress: number
	tags: string[]
	channelName?: string
}

export interface FilterOption {
	id: string
	label: string
	icon: "Search" | "Youtube" | "BookOpen" | "FileText"
}

export interface SortOption {
	id: string
	label: string
	icon: "Clock" | "CalendarDays" | "ArrowUpDown" | "FileText"
}

export function fetchContentData(): Promise<ContentItem[]>
export function processContentData(data: ContentItem[]): {
	content: ContentItem[]
	filterOptions: FilterOption[]
	sortOptions: SortOption[]
}
