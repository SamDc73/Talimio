import { motion } from "framer-motion"
import { useState } from "react"

import ErrorBoundary from "@/components/ErrorBoundary"

// Radix UI component initialization

import ContentCard from "@/components/ContentCard"
import { MainHeader } from "@/components/header/MainHeader"
import CelebrationOverlay from "@/features/home/components/CelebrationOverlay"
import ContentGrid from "@/features/home/components/ContentGrid"
import { DialogsContainer } from "@/features/home/components/dialogs/DialogsContainer"
import FabMenu from "@/features/home/components/FABMenu"
import FilterBadges from "@/features/home/components/FilterBadges"
import PinnedSection from "@/features/home/components/PinnedSection"
import SearchBar from "@/features/home/components/SearchBar"
import SkeletonGrid from "@/features/home/components/SkeletonGrid"
import WelcomeHeader from "@/features/home/components/WelcomeHeader"
import { useCelebration } from "@/features/home/hooks/useCelebration"
import { useContentData } from "@/features/home/hooks/useContentData"
import { useContentFilters } from "@/features/home/hooks/useContentFilters"
import { useContentHandlers } from "@/features/home/hooks/useContentHandlers"
import { useContentProgressSync } from "@/features/home/hooks/useContentProgressSync"
import { useDialogStates } from "@/features/home/hooks/useDialogStates"
import { usePinning } from "@/features/home/hooks/usePinning"
import RoadmapPromptModal from "@/features/roadmap/RoadmapPromptModal"
import { useProgress } from "@/hooks/useProgress"

export default function HomePage() {
	const [isGenerating, setIsGenerating] = useState(false)
	const [isFabExpanded, setIsFabExpanded] = useState(false)
	const [page, setPage] = useState(0)
	const itemsPerPage = 20

	// Use extracted hooks
	const dialogs = useDialogStates()
	const pinning = usePinning()
	const celebration = useCelebration()
	const filters = useContentFilters()

	// Use content data hook
	const {
		contentItems,
		setContentItems,
		filterOptions,
		sortOptions,
		isLoading: contentLoading,
		loadContentData,
	} = useContentData(filters, pinning)

	// Extract visible content IDs (pagination-aware)
	const filteredContent = filters.getFilteredAndSortedContent(contentItems)
	const start = page * itemsPerPage
	const end = start + itemsPerPage
	const visibleIds = filteredContent.slice(start, end).map((item) => item.id)

	// Load progress for visible items only
	const { data: progressData, isLoading: progressLoading } = useProgress(visibleIds)

	// Merge content with progress
	const contentWithProgress = filteredContent.slice(start, end).map((item) => ({
		...item,
		progress: progressData?.[item.id] || item.progress || 0,
	}))

	// Use content handlers hook
	const {
		handleGenerateCourse,
		handleRoadmapCreated,
		handleCardClick,
		handleDeleteItem,
		handleArchiveItem,
		handleTagsUpdated,
		handleBookUploaded,
		handleVideoAdded,
	} = useContentHandlers({
		filters,
		pinning,
		setContentItems,
		loadContentData,
		setIsGenerating,
	})

	// Use content progress sync hook for all content types
	// Note: We don't pass loadContentData to prevent infinite loops
	useContentProgressSync(setContentItems)

	// Apply filters and sorting using extracted hook
	const filteredAndSortedContent = filters.getFilteredAndSortedContent(contentItems)

	// Removed debug logging for performance

	const getActiveFilterLabel = () => {
		return filterOptions.find((option) => option.id === filters.activeFilter)?.label || "All Content"
	}

	const getActiveSortLabel = () => {
		return sortOptions.find((option) => option.id === filters.activeSort)?.label || "Last Opened"
	}

	const unpinned = pinning.getUnpinnedItems(contentWithProgress)
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

	const pinnedItems = pinning.getPinnedItems(contentWithProgress)

	// Total pages for pagination
	const totalPages = Math.ceil((filteredAndSortedContent.length || 0) / itemsPerPage)

	// Show loading skeleton while content is loading
	if (contentLoading) {
		return (
			<div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
				<MainHeader transparent />
				<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pt-28">
					<WelcomeHeader />
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
						<SkeletonGrid count={6} />
					</div>
				</div>
			</div>
		)
	}

	return (
		<ErrorBoundary>
			<CelebrationOverlay active={celebration.shouldShowCelebration(unpinned)} />
			<ErrorBoundary>
				<div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
					<MainHeader transparent />
					<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pt-28">
						<WelcomeHeader />

						<SearchBar
							searchQuery={filters.searchQuery}
							setSearchQuery={filters.setSearchQuery}
							isGenerateMode={filters.isGenerateMode}
							isYoutubeMode={filters.isYoutubeMode}
							isGenerating={isGenerating}
							onGenerateCourse={handleGenerateCourse}
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
							onGenerateRoadmap={() => dialogs.setShowRoadmapModal(true)}
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

						{filters && (
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
						)}

						<motion.div
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, delay: 0.3 }}
						>
							<PinnedSection pinnedItems={pinnedItems} renderCard={renderCard} />
							<ContentGrid
								isLoading={contentLoading}
								filteredAndSortedContent={contentWithProgress}
								visible={visible}
								unpinned={unpinned}
								showAll={filters.showAll}
								renderCard={renderCard}
								onShowMoreToggle={() => filters.setShowAll(!filters.showAll)}
								onGenerateCourse={() => filters.setIsGenerateMode(true)}
								onUploadBook={() => {
									dialogs.setShowUploadDialog(true)
								}}
								onAddYoutube={() => dialogs.setShowYoutubeDialog(true)}
								progressLoading={progressLoading}
							/>
							{/* Add pagination if we have more than one page */}
							{totalPages > 1 && (
								<div className="mt-8 flex justify-center">
									<div className="flex gap-2">
										<button
											type="button"
											onClick={() => setPage(Math.max(0, page - 1))}
											disabled={page === 0}
											className="px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-100/80 disabled:opacity-50"
										>
											Previous
										</button>
										<span className="px-4 py-2">
											Page {page + 1} of {totalPages}
										</span>
										<button
											type="button"
											onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
											disabled={page >= totalPages - 1}
											className="px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-100/80 disabled:opacity-50"
										>
											Next
										</button>
									</div>
								</div>
							)}
						</motion.div>
					</div>

					<FabMenu
						isFabExpanded={isFabExpanded}
						onToggleExpanded={() => setIsFabExpanded(!isFabExpanded)}
						onGenerateCourse={() => {
							filters.setIsGenerateMode(true)
							// Focus on search input after a short delay
							setTimeout(() => {
								const searchInput = document.querySelector('input[type="text"]')
								if (searchInput) searchInput.focus()
							}, 100)
						}}
						onGenerateRoadmap={() => dialogs.setShowRoadmapModal(true)}
						onUploadBook={() => {
							dialogs.setShowUploadDialog(true)
						}}
						onAddYoutube={() => dialogs.setShowYoutubeDialog(true)}
					/>

					<DialogsContainer dialogs={dialogs} onBookUploaded={handleBookUploaded} onVideoAdded={handleVideoAdded} />

					<RoadmapPromptModal
						open={dialogs.showRoadmapModal}
						onOpenChange={dialogs.setShowRoadmapModal}
						onRoadmapCreated={handleRoadmapCreated}
					/>
				</div>
			</ErrorBoundary>
		</ErrorBoundary>
	)
}
