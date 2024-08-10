import { ChevronRight, FileText } from "lucide-react"
import { useEffect, useState } from "react"
import { useToast } from "@/hooks/use-toast"
import { useBookProgress } from "@/hooks/useBookProgress"
import { extractBookChapters, getBookChapters } from "@/services/booksService"
import CompletionCheckbox from "./CompletionCheckbox"
import ProgressCircle from "./ProgressCircle"
import ProgressIndicator from "./ProgressIndicator"
import SidebarContainer from "./SidebarContainer"
import SidebarItem from "./SidebarItem"
import SidebarNav from "./SidebarNav"

/**
 * BookSidebar - Displays book table of contents with progress tracking
 *
 * IMPORTANT: Interactive Element Rules
 * 1. Never nest buttons/links inside other buttons/links
 * 2. Use CompletionCheckbox with asDiv={true} when inside interactive containers
 * 3. Keep clickable elements as siblings, not parent-child
 *
 * Pattern:
 * <Container>
 *   <InteractiveElement1 />
 *   <InteractiveElement2 />
 * </Container>
 *
 * @param {Object} book - The book object
 * @param {number} currentPage - Current page number
 * @param {Function} onChapterClick - Handler for chapter navigation
 * @param {number} progressPercentage - Overall progress percentage
 */
function BookSidebar({ book, bookId, currentPage = 1, onChapterClick, progressPercentage = 0 }) {
	const [ExpandedChapters, SetExpandedChapters] = useState([0])
	const [ApiChapters, SetApiChapters] = useState([])
	const [IsExtracting, SetIsExtracting] = useState(false)
	const [IsLoadingChapters, SetIsLoadingChapters] = useState(false)
	const [optimisticCompletions, setOptimisticCompletions] = useState({})
	const { toast } = useToast()

	// Use the standardized hook with bookId prop
	const { progress, toggleCompletion, isCompleted, batchUpdate, refetch } = useBookProgress(bookId)

	/**
	 * Get all children IDs recursively
	 */
	const getAllChildrenIds = (section) => {
		let ids = []
		if (section.children?.length > 0) {
			for (const child of section.children) {
				ids.push(child.id)
				ids = ids.concat(getAllChildrenIds(child))
			}
		}
		return ids
	}

	/**
	 * Count total leaf chapters (chapters without children)
	 * This matches the backend's calculation
	 */
	const CountTotalLeafChapters = (chapters) => {
		let count = 0

		const countLeaves = (items) => {
			for (const item of items) {
				if (!item.children || item.children.length === 0) {
					// This is a leaf node
					count++
				} else {
					// Has children, recurse
					countLeaves(item.children)
				}
			}
		}

		if (Array.isArray(chapters)) {
			countLeaves(chapters)
		}

		return count
	}

	// Helper to check if chapter is completed (with optimistic state)
	const isChapterCompleted = (chapterId) => {
		// Check optimistic state first
		if (chapterId in optimisticCompletions) {
			return optimisticCompletions[chapterId]
		}
		// Fall back to actual state
		return isCompleted(chapterId)
	}

	/**
	 * Toggle completion for a section/chapter
	 */
	const ToggleSectionCompletion = async (section, totalChapters) => {
		const hasChildren = section.children?.length > 0

		if (hasChildren) {
			// For parent chapters, toggle all children
			const allChildren = getAllChildrenIds(section)
			const allIds = [section.id, ...allChildren]
			const completedCount = allIds.filter((id) => isChapterCompleted(id)).length
			const newStatus = completedCount < allIds.length

			// Optimistic update
			const newOptimistic = {}
			allIds.forEach((id) => {
				newOptimistic[id] = newStatus
			})
			setOptimisticCompletions((prev) => ({ ...prev, ...newOptimistic }))

			try {
				const updates = allIds.map((id) => ({
					itemId: id,
					completed: newStatus,
				}))
				await batchUpdate(updates, totalChapters)
				// Clear optimistic state on success
				setOptimisticCompletions((prev) => {
					const newState = { ...prev }
					allIds.forEach((id) => delete newState[id])
					return newState
				})
			} catch (_error) {
				// Revert optimistic update on error
				setOptimisticCompletions((prev) => {
					const newState = { ...prev }
					allIds.forEach((id) => delete newState[id])
					return newState
				})
				toast({
					title: "Error",
					description: "Failed to update chapter progress",
					variant: "destructive",
				})
			}
		} else {
			// For single sections, just toggle
			const chapterId = section.id

			// Optimistic update
			setOptimisticCompletions((prev) => ({
				...prev,
				[chapterId]: !isChapterCompleted(chapterId),
			}))

			try {
				await toggleCompletion(chapterId, totalChapters)
				// Clear optimistic state on success
				setOptimisticCompletions((prev) => {
					const newState = { ...prev }
					delete newState[chapterId]
					return newState
				})
			} catch (_error) {
				// Revert optimistic update on error
				setOptimisticCompletions((prev) => {
					const newState = { ...prev }
					delete newState[chapterId]
					return newState
				})
				toast({
					title: "Error",
					description: "Failed to update chapter progress",
					variant: "destructive",
				})
			}
		}
	}

	/**
	 * Calculate chapter progress
	 */
	const getChapterProgress = (chapter) => {
		if (!chapter.children?.length) {
			return isChapterCompleted(chapter.id) ? 100 : 0
		}
		// Calculate progress for chapters with children
		const allChildren = getAllChildrenIds(chapter)
		const allIds = [chapter.id, ...allChildren]
		const completedCount = allIds.filter((id) => isChapterCompleted(id)).length
		return Math.round((completedCount / allIds.length) * 100)
	}

	/**
	 * Fetch chapters from API only once per book
	 * Skip if book already has tableOfContents to prevent unnecessary API calls
	 */
	useEffect(() => {
		if (!bookId) return

		// Skip if already have chapters from book object
		if (book?.tableOfContents?.length > 0) {
			return
		}

		async function fetchChapters() {
			SetIsLoadingChapters(true)
			try {
				const chapters = await getBookChapters(bookId)
				SetApiChapters(chapters || [])
			} catch (error) {
				// Don't log error if it's expected (404 when no chapters exist)
				if (!error.message?.includes("404")) {
				}
				SetApiChapters([])
			} finally {
				SetIsLoadingChapters(false)
			}
		}

		fetchChapters()
	}, [bookId, book?.tableOfContents?.length])

	/**
	 * Extract chapters using AI
	 */
	const handleExtractChapters = async () => {
		SetIsExtracting(true)
		try {
			const result = await extractBookChapters(bookId)
			toast({
				title: "Chapters extracted",
				description: `Successfully extracted ${result.count || 0} chapters`,
			})

			// Refresh chapters
			const chapters = await getBookChapters(book.id)
			SetApiChapters(chapters || [])

			// Refresh progress data
			await refetch()
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to extract chapters",
				variant: "destructive",
			})
		} finally {
			SetIsExtracting(false)
		}
	}

	/**
	 * Check if current page is in chapter
	 */
	const isPageInChapter = (chapter) => {
		if (chapter.startPage && chapter.endPage) {
			return currentPage >= chapter.startPage && currentPage <= chapter.endPage
		}
		if (chapter.page) {
			return currentPage === chapter.page
		}
		if (chapter.children?.length > 0) {
			return chapter.children.some((section) => {
				if (section.startPage && section.endPage) {
					return currentPage >= section.startPage && currentPage <= section.endPage
				}
				return currentPage === section.page
			})
		}
		return false
	}

	/**
	 * Toggle chapter expansion
	 */
	const handleToggleChapter = (chapterIndex) => {
		SetExpandedChapters((prev) =>
			prev.includes(chapterIndex) ? prev.filter((idx) => idx !== chapterIndex) : [...prev, chapterIndex]
		)
	}

	// Auto-expand chapter containing current page
	useEffect(() => {
		const chapters = book?.tableOfContents || ApiChapters
		if (chapters.length > 0 && currentPage) {
			const currentChapterIndex = chapters.findIndex((chapter) => {
				// Inline isPageInChapter logic to avoid function dependency
				if (chapter.startPage && chapter.endPage) {
					return currentPage >= chapter.startPage && currentPage <= chapter.endPage
				}
				if (chapter.page) {
					return currentPage === chapter.page
				}
				if (chapter.children?.length > 0) {
					return chapter.children.some((section) => {
						if (section.startPage && section.endPage) {
							return currentPage >= section.startPage && currentPage <= section.endPage
						}
						return currentPage === section.page
					})
				}
				return false
			})

			// Only expand if not already expanded to avoid infinite loops
			SetExpandedChapters((prev) => {
				if (currentChapterIndex >= 0 && !prev.includes(currentChapterIndex)) {
					return [...prev, currentChapterIndex]
				}
				return prev
			})
		}
	}, [currentPage, book?.tableOfContents, ApiChapters])

	if (!book) return null

	const chapters = book.tableOfContents?.length > 0 ? book.tableOfContents : ApiChapters

	const overallProgress = progress.percentage || progressPercentage || 0

	// Calculate total leaf chapters for progress calculation
	const totalLeafChapters = CountTotalLeafChapters(chapters)

	// Empty state
	if (!chapters.length) {
		return (
			<SidebarContainer>
				<div className="px-4 pt-20 pb-4">
					<div className="text-center text-zinc-500 text-sm mt-8">
						<FileText className="w-12 h-12 mx-auto mb-4 text-zinc-300" />
						<p>No table of contents available</p>
						{!IsLoadingChapters && (
							<>
								<p className="text-xs mt-2">This book doesn't have chapter information.</p>
								<button
									type="button"
									onClick={handleExtractChapters}
									disabled={IsExtracting}
									className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
								>
									<FileText className="w-4 h-4" />
									{IsExtracting ? "Extracting..." : "Extract Chapters"}
								</button>
							</>
						)}
					</div>
				</div>
			</SidebarContainer>
		)
	}

	return (
		<SidebarContainer>
			<ProgressIndicator progress={overallProgress} variant="book" suffix="Read">
				<span className="text-xs text-zinc-500">
					{currentPage && book.totalPages ? `Page ${currentPage} of ${book.totalPages}` : "Loading..."}
				</span>
			</ProgressIndicator>

			<SidebarNav>
				{chapters.map((chapter, chapterIndex) => {
					const isExpanded = ExpandedChapters.includes(chapterIndex)
					const chapterProgress = getChapterProgress(chapter)
					const isActive = isPageInChapter(chapter)
					const hasChildren = chapter.children?.length > 0
					const isCompleted = chapterProgress === 100

					// For chapters without children, show checkbox
					if (!hasChildren) {
						return (
							<div
								key={`chapter_${chapterIndex}_${chapter.id}`}
								className={`rounded-2xl border ${
									isActive ? "border-blue-200 bg-blue-50/50" : "border-border bg-white"
								} shadow-sm overflow-hidden`}
							>
								<div className="flex items-center gap-3 px-4 py-3">
									<ProgressCircle number={chapterIndex + 1} progress={chapterProgress} variant="book" />
									<CompletionCheckbox
										asDiv={true}
										className="completion-checkbox"
										isCompleted={isCompleted}
										onClick={(e) => {
											e.stopPropagation()
											ToggleSectionCompletion(chapter, totalLeafChapters)
										}}
										variant="book"
									/>
									<button
										type="button"
										onClick={() => {
											onChapterClick?.(chapter.page || chapter.startPage, chapter.id)
										}}
										className="flex-1 text-left hover:underline"
									>
										<span className="line-clamp-2 text-sm font-semibold">{chapter.title}</span>
									</button>
								</div>
							</div>
						)
					}

					// For chapters with children
					return (
						<div
							key={`chapter_${chapterIndex}_${chapter.id}`}
							className={`rounded-2xl border ${
								isActive ? "border-blue-200 bg-blue-50/50" : "border-border bg-white"
							} shadow-sm overflow-hidden`}
						>
							<div className="flex items-center gap-3 px-4 py-3">
								<ProgressCircle number={chapterIndex + 1} progress={chapterProgress} variant="book" />
								<CompletionCheckbox
									asDiv={true}
									className="completion-checkbox"
									isCompleted={isCompleted}
									onClick={(e) => {
										e.stopPropagation()
										ToggleSectionCompletion(chapter, totalLeafChapters)
									}}
									variant="book"
								/>
								<button
									type="button"
									onClick={() => handleToggleChapter(chapterIndex)}
									className="flex-1 flex items-center justify-between text-left"
								>
									<span className="line-clamp-2 text-sm font-semibold">{chapter.title}</span>
									<ChevronRight
										className={`w-4 h-4 text-zinc-400 transition-transform duration-200 ${
											isExpanded ? "rotate-90 text-blue-600" : "rotate-0"
										}`}
									/>
								</button>
							</div>
							{isExpanded && (
								<div className="px-4 py-2 space-y-2 border-t border-border">
									<ol>
										{chapter.children.map((section, sectionIndex) => {
											const isSectionCompleted = isChapterCompleted(section.id)
											const isSectionActive =
												currentPage === section.page ||
												(section.startPage &&
													section.endPage &&
													currentPage >= section.startPage &&
													currentPage <= section.endPage)

											return (
												<SidebarItem
													key={`${chapter.id}_${sectionIndex}_${section.id}`}
													title={section.title}
													isActive={isSectionActive}
													isCompleted={isSectionCompleted}
													onClick={() => onChapterClick?.(section.page, section.id)}
													variant="book"
													leftContent={
														<CompletionCheckbox
															asDiv={true}
															className="completion-checkbox"
															isCompleted={isSectionCompleted}
															onClick={(e) => {
																e.stopPropagation()
																ToggleSectionCompletion(section, totalLeafChapters)
															}}
															variant="book"
														/>
													}
												/>
											)
										})}
									</ol>
								</div>
							)}
						</div>
					)
				})}
			</SidebarNav>
		</SidebarContainer>
	)
}

export default BookSidebar
