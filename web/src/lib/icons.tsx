import { ArrowUpDown, BookOpen, CalendarDays, Clock, FileText, Layers, Search, Youtube } from "lucide-react"
import React from "react"
import type { FilterOption, RawFilterOption, RawSortOption, SortOption } from "@/types/content"

type IconType = {
	className?: string
	size?: number
}

export const IconMap: Record<string, React.ComponentType<IconType>> = {
	Search,
	BookOpen,
	FileText,
	Youtube,
	Layers,
	Clock,
	CalendarDays,
	ArrowUpDown,
}

export function getIcon(iconName: string, props: IconType = {}): React.ReactElement | null {
	const IconComponent = IconMap[iconName]
	return IconComponent ? React.createElement(IconComponent, props) : null
}

// Process raw filter options into component-ready options
export function processFilterOptions(options: RawFilterOption[]): FilterOption[] {
	return options.map((option) => ({
		...option,
		icon: getIcon(option.icon) || <div>Icon not found</div>,
	}))
}

// Process raw sort options into component-ready options
export function processSortOptions(options: RawSortOption[]): SortOption[] {
	return options.map((option) => ({
		...option,
		icon: getIcon(option.icon) || <div>Icon not found</div>,
	}))
}
