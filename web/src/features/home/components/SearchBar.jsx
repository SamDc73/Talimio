import { motion } from "framer-motion"
import { Search, Sparkles, X } from "lucide-react"
import { Button } from "@/components/Button"
import { Input } from "@/components/Input"
import { YouTubeMark } from "@/components/YouTubeMark"
import FilterPopover from "./FilterPopover"

function SearchBar({
	searchQuery,
	setSearchQuery,
	isGenerateMode,
	isYoutubeMode,
	isGenerating,
	onGenerateCourse,
	onYoutubeAdd,
	onSetMode,
	// Filter props
	filterOptions,
	sortOptions,
	activeFilter,
	setActiveFilter,
	archiveFilter,
	setArchiveFilter,
	tagFilter,
	setTagFilter,
	activeSort,
	setActiveSort,
	sortDirection,
	toggleSortDirection,
}) {
	let searchModeBackgroundClass = ""
	let searchModeIcon = <Search className="text-muted-foreground" size={20} />
	let searchPlaceholder = "Search your courses and books..."
	if (isGenerateMode) {
		searchModeBackgroundClass = "bg-course/10"
		searchModeIcon = <Sparkles className="text-course" size={20} />
		searchPlaceholder = "What do you want to learn about?"
	} else if (isYoutubeMode) {
		searchModeBackgroundClass = "bg-video/10"
		searchModeIcon = <YouTubeMark className="size-5 text-video" />
		searchPlaceholder = "Paste a YouTube URL or search for videos..."
	}

	const renderActionControls = () => {
		if (isGenerateMode) {
			return (
				<>
					<div className="h-8 w-px bg-border/60" />
					<Button variant="ghost" size="sm" onClick={() => onSetMode(null)} className="h-9 text-muted-foreground">
						Cancel
					</Button>
					<Button
						size="sm"
						onClick={onGenerateCourse}
						disabled={!searchQuery.trim() || isGenerating}
						className="h-9 bg-course text-course-text hover:bg-course-accent"
					>
						{isGenerating ? "Generating..." : "Generate"}
					</Button>
				</>
			)
		}

		if (isYoutubeMode) {
			return (
				<>
					<div className="h-8 w-px bg-border/60" />
					<Button variant="ghost" size="sm" onClick={() => onSetMode(null)} className="h-9 text-muted-foreground">
						Cancel
					</Button>
					<Button
						size="sm"
						onClick={() => {
							if (searchQuery.trim()) {
								onYoutubeAdd(searchQuery)
								onSetMode(null)
							}
						}}
						disabled={!searchQuery.trim()}
						className="h-9 bg-video text-video-text hover:bg-video-accent"
					>
						Add Video
					</Button>
				</>
			)
		}

		return (
			<>
				<Button size="sm" onClick={onGenerateCourse} className="h-9 gap-2xs shadow-sm">
					<Sparkles className="size-4" />
					Generate Course
				</Button>
				<div className="h-8 w-px bg-border/60" />
				<FilterPopover
					filterOptions={filterOptions}
					sortOptions={sortOptions}
					activeFilter={activeFilter}
					setActiveFilter={setActiveFilter}
					archiveFilter={archiveFilter}
					setArchiveFilter={setArchiveFilter}
					tagFilter={tagFilter}
					setTagFilter={setTagFilter}
					activeSort={activeSort}
					setActiveSort={setActiveSort}
					sortDirection={sortDirection}
					toggleSortDirection={toggleSortDirection}
				/>
			</>
		)
	}

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5, delay: 0.1 }}
			className="mx-auto mb-lg max-w-container-2xl"
		>
			<div
				className={`flex items-center gap-3 rounded-xl border border-border/50 bg-card/95 px-3 py-2 shadow-sm transition-colors hover:border-border/70 ${searchModeBackgroundClass}`}
			>
				{searchModeIcon}
				<Input
					type="text"
					placeholder={searchPlaceholder}
					className="h-9 flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
					value={searchQuery}
					onChange={(e) => setSearchQuery(e.target.value)}
				/>
				{searchQuery && (
					<Button
						variant="ghost"
						size="icon"
						onClick={() => setSearchQuery("")}
						className="size-8 rounded-md text-muted-foreground/70 hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0"
					>
						<X className="size-4" />
					</Button>
				)}
				{renderActionControls()}
			</div>
		</motion.div>
	)
}

export default SearchBar
