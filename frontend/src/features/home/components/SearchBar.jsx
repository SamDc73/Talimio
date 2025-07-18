import { motion } from "framer-motion";
import { Search, Sparkles, X, Youtube } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import FilterPopover from "./FilterPopover";

const SearchBar = ({
	searchQuery,
	setSearchQuery,
	isGenerateMode,
	isYoutubeMode,
	isGenerating,
	onGenerateCourse,
	onYoutubeAdd,
	onSetMode,
	onGenerateRoadmap,
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
}) => {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5, delay: 0.1 }}
			className="max-w-2xl mx-auto mb-6"
		>
			<div className="bg-white rounded-2xl shadow-sm p-2 border border-border transition-all hover:shadow-md">
				<div className="flex items-center">
					<div
						className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-xl transition-all ${
							isGenerateMode
								? "bg-course/10"
								: isYoutubeMode
									? "bg-video/10"
									: ""
						}`}
					>
						{isGenerateMode ? (
							<Sparkles className="text-course" size={20} />
						) : isYoutubeMode ? (
							<Youtube className="text-video" size={20} />
						) : (
							<Search className="text-muted-foreground" size={20} />
						)}
						<Input
							type="text"
							placeholder={
								isGenerateMode
									? "What do you want to learn about?"
									: isYoutubeMode
										? "Paste a YouTube URL or search for videos..."
										: "Search your courses and books..."
							}
							className="border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
						/>
						{searchQuery && (
							<Button
								variant="ghost"
								size="icon"
								onClick={() => setSearchQuery("")}
								className="h-8 w-8"
							>
								<X className="h-4 w-4" />
							</Button>
						)}
					</div>

					<div className="flex items-center gap-2 pl-2">
						{isGenerateMode ? (
							<>
								<div className="h-8 w-px bg-border" />
								<Button
									variant="ghost"
									size="sm"
									onClick={() => onSetMode(null)}
									className="text-muted-foreground"
								>
									Cancel
								</Button>
								<Button
									size="sm"
									onClick={onGenerateCourse}
									disabled={!searchQuery.trim() || isGenerating}
									className="bg-course hover:bg-course-accent text-white"
								>
									{isGenerating ? "Generating..." : "Generate"}
								</Button>
							</>
						) : isYoutubeMode ? (
							<>
								<div className="h-8 w-px bg-border" />
								<Button
									variant="ghost"
									size="sm"
									onClick={() => onSetMode(null)}
									className="text-muted-foreground"
								>
									Cancel
								</Button>
								<Button
									size="sm"
									onClick={() => {
										if (searchQuery.trim()) {
											onYoutubeAdd(searchQuery);
											onSetMode(null);
										}
									}}
									disabled={!searchQuery.trim()}
									className="bg-video hover:bg-video-accent text-white"
								>
									Add Video
								</Button>
							</>
						) : (
							<>
								<Button
									onClick={onGenerateRoadmap}
									size="sm"
									className="bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 text-white flex items-center gap-1"
								>
									<Sparkles className="h-3.5 w-3.5" />
									Generate Roadmap
								</Button>
								<div className="h-8 w-px bg-border" />
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
						)}
					</div>
				</div>
			</div>
		</motion.div>
	);
};

export default SearchBar;
