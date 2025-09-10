import { ArrowUpDown, BookOpen, CalendarDays, Clock, FileText, Layers, Search, Youtube } from "lucide-react"

// Map icon names to components
export const ICON_MAP = {
	Search: Search,
	BookOpen: BookOpen,
	FileText: FileText,
	Youtube: Youtube,
	Layers: Layers,
	Clock: Clock,
	CalendarDays: CalendarDays,
	ArrowUpDown: ArrowUpDown,
}

// Helper function to render icon by name
export function renderIcon(iconName, className = "h-4 w-4 mr-2") {
	const Icon = ICON_MAP[iconName]
	return Icon ? <Icon className={className} /> : null
}
