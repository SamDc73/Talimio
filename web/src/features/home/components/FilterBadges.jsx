import { motion } from "framer-motion"
import { X } from "lucide-react"

import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"

const FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME =
	"ml-3xs size-md p-0 text-muted-foreground/65 hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0"

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
			className="mx-auto mb-xl flex max-w-container-2xl flex-wrap items-center gap-2xs"
		>
			{activeFilter !== "all" && (
				<Badge variant="outline" className="bg-card">
					{getActiveFilterLabel()}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onFilterChange("all")}
						className={FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME}
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
						className={FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME}
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
						className={FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME}
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
						className={FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME}
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
						className={FILTER_BADGE_REMOVE_BUTTON_CLASS_NAME}
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
					className="ml-auto h-lg px-xs text-xs text-muted-foreground"
				>
					Reset All
				</Button>
			)}
		</motion.div>
	)
}
