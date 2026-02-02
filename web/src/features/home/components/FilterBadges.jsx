import { motion } from "framer-motion"
import { X } from "lucide-react"

import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"

export default function FilterBadges({
	activeFilter,
	archiveFilter,
	activeSort,
	sortDirection,
	tagFilter,
	getActiveFilterLabel,
	getActiveSortLabel,
	onFilterChange,
	onArchiveFilterChange,
	onSortChange,
	onSortDirectionChange,
	onTagFilterChange,
	onResetAll,
}) {
	const hasActiveFilters =
		activeFilter !== "all" || activeSort !== "last-accessed" || sortDirection !== "desc" || tagFilter

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3, delay: 0.2 }}
			className="max-w-2xl mx-auto mb-8 flex flex-wrap items-center gap-2"
		>
			{activeFilter !== "all" && (
				<Badge variant="outline" className="bg-card">
					{getActiveFilterLabel()}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onFilterChange("all")}
						className="size-4  p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
					>
						<X className="size-3 " />
						<span className="sr-only">Remove filter</span>
					</Button>
				</Badge>
			)}

			{archiveFilter !== "active" && (
				<Badge variant="outline" className="bg-card">
					{archiveFilter === "archived" ? "Archived Content" : "All Content"}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onArchiveFilterChange("active")}
						className="size-4  p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
					>
						<X className="size-3 " />
						<span className="sr-only">Reset archive filter</span>
					</Button>
				</Badge>
			)}

			{activeSort !== "last-accessed" && (
				<Badge variant="outline" className="bg-card">
					Sorted by: {getActiveSortLabel()}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onSortChange("last-accessed")}
						className="size-4  p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
					>
						<X className="size-3 " />
						<span className="sr-only">Remove sort</span>
					</Button>
				</Badge>
			)}

			{sortDirection !== "desc" && (
				<Badge variant="outline" className="bg-card">
					{sortDirection === "asc" ? "Oldest First" : "Newest First"}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onSortDirectionChange("desc")}
						className="size-4  p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
					>
						<X className="size-3 " />
						<span className="sr-only">Remove sort direction</span>
					</Button>
				</Badge>
			)}

			{tagFilter && (
				<Badge variant="outline" className="bg-card">
					Tag: {tagFilter}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onTagFilterChange("")}
						className="size-4  p-0 ml-1 text-muted-foreground hover:text-muted-foreground"
					>
						<X className="size-3 " />
						<span className="sr-only">Remove tag filter</span>
					</Button>
				</Badge>
			)}

			{hasActiveFilters && (
				<Button
					variant="ghost"
					size="sm"
					onClick={onResetAll}
					className="text-xs text-muted-foreground h-7 px-2 ml-auto"
				>
					Reset All
				</Button>
			)}
		</motion.div>
	)
}
