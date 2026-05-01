import { motion } from "framer-motion"
import { useState } from "react"

import ErrorBoundary from "@/components/ErrorBoundary"

// Radix UI component initialization

import { MainHeader } from "@/components/header/MainHeader"
import ContentCard from "@/features/home/components/ContentCard"
import ContentGrid from "@/features/home/components/ContentGrid"
import { BookUploadDialog } from "@/features/home/components/dialogs/BookUploadDialog"
import CoursePromptModal from "@/features/home/components/dialogs/CoursePromptModal"
import { YouTubeDialog } from "@/features/home/components/dialogs/YouTubeDialog"
import FabMenu from "@/features/home/components/FabMenu"
import FilterBadges from "@/features/home/components/FilterBadges"
import PinnedSection from "@/features/home/components/PinnedSection"
import SearchBar from "@/features/home/components/SearchBar"
import SkeletonGrid from "@/features/home/components/SkeletonGrid"
import WelcomeHeader from "@/features/home/components/WelcomeHeader"
import { useContentData } from "@/features/home/hooks/use-content-data"
import { useContentFilters } from "@/features/home/hooks/use-content-filters"
import { useContentHandlers } from "@/features/home/hooks/use-content-handlers"
import { useDialogStates } from "@/features/home/hooks/use-dialog-states"
import { usePinning } from "@/features/home/hooks/use-pinning"

export default function HomePage() {
	const isGenerating = false
	const [isFabExpanded, setIsFabExpanded] = useState(false)

	// Use extracted hooks
	const dialogs = useDialogStates()
	const pinning = usePinning()
	const filters = useContentFilters()

	// Use content data hook
	const {
		contentItems,
		filterOptions,
		sortOptions,
		isLoading: contentLoading,
		hasMoreContent,
		loadContentData,
		loadRemainingContent,
	} = useContentData(filters, pinning)

	// Apply filters and sorting using extracted hook
	const filteredAndSortedContent = filters.getFilteredAndSortedContent(contentItems)

	// Use content handlers hook
	const {
		handleCourseCreated,
		handleCardClick,
		handleDeleteItem,
		handleArchiveItem,
		handleTagsUpdated,
		handleBookUploaded,
		handleVideoAdded,
	} = useContentHandlers({
		filters,
		pinning,
		loadContentData,
	})

	// Removed debug logging for performance

	const getActiveFilterLabel = () => {
		return filterOptions.find((option) => option.id === filters.activeFilter)?.label || "All Content"
	}

	const getActiveSortLabel = () => {
		return sortOptions.find((option) => option.id === filters.activeSort)?.label || "Last Opened"
	}

	const unpinned = pinning.getUnpinnedItems(filteredAndSortedContent)
	const visible = filters.showAll ? unpinned : unpinned.slice(0, 3)

	const renderCard = (item, i) => (
		<ContentCard
			key={item.id}
			item={item}
			index={i}
			pinned={pinning.pins[item.type]?.includes(item.id)}
			onTogglePin={() => pinning.togglePin(item.type, item.id)}
			onDelete={handleDeleteItem}
			onArchive={handleArchiveItem}
			onTagsUpdated={handleTagsUpdated}
			onClick={() => handleCardClick(item)}
		/>
	)

	const pinnedItems = pinning.getPinnedItems(filteredAndSortedContent)

	const handleShowMoreToggle = async () => {
		if (!filters.showAll && hasMoreContent) {
			await loadRemainingContent()
		}

		filters.setShowAll(!filters.showAll)
	}

	// Show loading skeleton while content is loading
	if (contentLoading) {
		return (
			<div className="min-h-screen bg-linear-to-b from-background to-muted/40">
				<MainHeader transparent />
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-xl pt-3xl">
					<WelcomeHeader />
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg mt-lg">
						<SkeletonGrid count={6} />
					</div>
				</div>
			</div>
		)
	}

	return (
		<ErrorBoundary>
			<ErrorBoundary>
				<div className="min-h-screen bg-linear-to-b from-background to-muted/40">
					<MainHeader transparent />
					<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-xl pt-3xl">
						<WelcomeHeader />

						<SearchBar
							searchQuery={filters.searchQuery}
							setSearchQuery={filters.setSearchQuery}
							isGenerateMode={filters.isGenerateMode}
							isYoutubeMode={filters.isYoutubeMode}
							isGenerating={isGenerating}
							onGenerateCourse={() => dialogs.setShowCourseModal(true)}
							onYoutubeAdd={(query) => {
								dialogs.setYoutubeUrl(query)
								dialogs.setShowYoutubeDialog(true)
							}}
							onSetMode={(mode) => {
								if (mode === "generate") {
									filters.setIsGenerateMode(true)
									filters.setIsYoutubeMode(false)
								} else if (mode === "youtube") {
									filters.setIsYoutubeMode(true)
									filters.setIsGenerateMode(false)
								} else {
									filters.setIsGenerateMode(false)
									filters.setIsYoutubeMode(false)
								}
							}}
							// Filter props
							filterOptions={filterOptions}
							sortOptions={sortOptions}
							activeFilter={filters.activeFilter}
							setActiveFilter={filters.setActiveFilter}
							archiveFilter={filters.archiveFilter}
							setArchiveFilter={filters.setArchiveFilter}
							tagFilter={filters.tagFilter}
							setTagFilter={filters.setTagFilter}
							activeSort={filters.activeSort}
							setActiveSort={filters.setActiveSort}
							sortDirection={filters.sortDirection}
							toggleSortDirection={filters.toggleSortDirection}
						/>

						<FilterBadges
							activeFilter={filters.activeFilter}
							archiveFilter={filters.archiveFilter}
							activeSort={filters.activeSort}
							sortDirection={filters.sortDirection}
							tagFilter={filters.tagFilter}
							getActiveFilterLabel={getActiveFilterLabel}
							getActiveSortLabel={getActiveSortLabel}
							onFilterChange={filters.setActiveFilter}
							onArchiveFilterChange={filters.setArchiveFilter}
							onSortChange={filters.setActiveSort}
							onSortDirectionChange={filters.setSortDirection}
							onTagFilterChange={filters.setTagFilter}
							onResetAll={() => {
								filters.setActiveFilter("all")
								filters.setActiveSort("last-accessed")
								filters.setSortDirection("desc")
								filters.setTagFilter("")
							}}
						/>

						<motion.div
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, delay: 0.3 }}
						>
							<PinnedSection pinnedItems={pinnedItems} renderCard={renderCard} />
							<ContentGrid
								isLoading={contentLoading}
								filteredAndSortedContent={filteredAndSortedContent}
								visible={visible}
								unpinned={unpinned}
								showAll={filters.showAll}
								hasMoreContent={hasMoreContent}
								renderCard={renderCard}
								onShowMoreToggle={handleShowMoreToggle}
								onGenerateCourse={() => filters.setIsGenerateMode(true)}
								onUploadBook={() => {
									dialogs.setShowUploadDialog(true)
								}}
								onAddYoutube={() => dialogs.setShowYoutubeDialog(true)}
							/>
						</motion.div>
					</div>

					<FabMenu
						isFabExpanded={isFabExpanded}
						onToggleExpanded={() => setIsFabExpanded(!isFabExpanded)}
						onGenerateCourse={() => dialogs.setShowCourseModal(true)}
						onUploadBook={() => {
							dialogs.setShowUploadDialog(true)
						}}
						onAddYoutube={() => dialogs.setShowYoutubeDialog(true)}
					/>

					<BookUploadDialog
						open={dialogs.showUploadDialog}
						onOpenChange={dialogs.setShowUploadDialog}
						onBookUploaded={handleBookUploaded}
					/>

					<YouTubeDialog
						open={dialogs.showYoutubeDialog}
						onOpenChange={dialogs.setShowYoutubeDialog}
						onVideoAdded={handleVideoAdded}
					/>

					<CoursePromptModal
						isOpen={dialogs.showCourseModal}
						onClose={() => dialogs.setShowCourseModal(false)}
						onSuccess={handleCourseCreated}
					/>
				</div>
			</ErrorBoundary>
		</ErrorBoundary>
	)
}
