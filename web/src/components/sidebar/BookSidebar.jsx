import { FileText } from "lucide-react";
import { useCallback, useEffect, useState, useMemo } from "react";
import { extractBookChapters, getBookChapters } from "@/services/booksService";
import { useTocProgress } from "@/services/tocProgressService";
import useAppStore from "@/stores/useAppStore";
import CompletionCheckbox from "./CompletionCheckbox";
import ExpandableSection from "./ExpandableSection";
import ProgressCircle from "./ProgressCircle";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarItem from "./SidebarItem";
import SidebarNav from "./SidebarNav";

// Stable default objects to prevent re-renders
const DEFAULT_STATS = {
	totalSections: 0,
	completedSections: 0,
	percentage: 0,
};

const EMPTY_TOC_PROGRESS = {};

/**
 * Clean BookSidebar matching the course sidebar design
 */
function BookSidebar({
	book,
	currentPage = 1,
	onChapterClick,
	progressPercentage = 0,
}) {
	const [expandedChapters, setExpandedChapters] = useState([0]);
	const [apiChapters, setApiChapters] = useState([]);
	const [isExtracting, setIsExtracting] = useState(false);

	const stats = useAppStore(
		useCallback(
			(state) => {
				if (!book?.id) return DEFAULT_STATS;
				return state.books.progressStats[book.id] || DEFAULT_STATS;
			},
			[book?.id]
		),
	);

	// Zustand store actions
	const setLoading = useAppStore((state) => state.setLoading);
	const batchUpdateTocProgress = useAppStore(
		(state) => state.batchUpdateTocProgress,
	);

	// Use enhanced ToC progress hook
	const tocProgressUtils = useTocProgress(book?.id);
	// Get completedSections directly from store to ensure reactivity
	const tocProgress = useAppStore(
		useCallback(
			(state) => {
				if (!book?.id) return EMPTY_TOC_PROGRESS;
				return state.books.tocProgress[book.id] || EMPTY_TOC_PROGRESS;
			},
			[book?.id]
		),
	);
	const completedSections = useMemo(
		() => new Set(
			Object.entries(tocProgress)
				.filter(([_, completed]) => completed)
				.map(([sectionId, _]) => sectionId),
		),
		[tocProgress]
	);

	/**
	 * Get all children IDs recursively
	 */
	const getAllChildrenIds = useCallback((section) => {
		let ids = [];
		if (section.children?.length > 0) {
			for (const child of section.children) {
				ids.push(child.id);
				ids = ids.concat(getAllChildrenIds(child));
			}
		}
		return ids;
	}, []);

	/**
	 * Toggle completion for a section/chapter
	 */
	const toggleSectionCompletion = useCallback(
		(section) => {
			const hasChildren = section.children?.length > 0;

			if (hasChildren) {
				// For parent chapters, toggle all children
				const allChildren = getAllChildrenIds(section);
				const allIds = [section.id, ...allChildren];
				const completedCount = allIds.filter((id) =>
					completedSections.has(id),
				).length;
				const newStatus = completedCount < allIds.length;

				const updates = allIds.map((id) => ({
					sectionId: id,
					isCompleted: newStatus,
				}));
				batchUpdateTocProgress(book.id, updates);
			} else {
				// For single sections, just toggle
				const isCompleted = tocProgressUtils.isCompleted(section.id);
				tocProgressUtils.updateSection(section.id, !isCompleted);
			}
		},
		[
			getAllChildrenIds,
			completedSections,
			tocProgressUtils,
			batchUpdateTocProgress,
			book?.id,
		],
	);

	/**
	 * Calculate chapter progress
	 */
	const getChapterProgress = useCallback(
		(chapter) => {
			if (!chapter.children?.length) {
				return tocProgressUtils.isCompleted(chapter.id) ? 100 : 0;
			}
			return tocProgressUtils.getChapterProgress(chapter);
		},
		[tocProgressUtils],
	);

	/**
	 * Fetch chapters from API
	 */
	useEffect(() => {
		if (!book?.id) return;

		async function fetchChapters() {
			setLoading("book-chapters", true);
			try {
				const chapters = await getBookChapters(book.id);
				setApiChapters(chapters || []);
			} catch (error) {
				console.error("Failed to fetch chapters:", error);
				setApiChapters([]);
			} finally {
				setLoading("book-chapters", false);
			}
		}

		fetchChapters();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [book?.id, setLoading]); // setLoading is stable, intentionally excluded to prevent infinite re-renders

	/**
	 * Extract chapters using AI
	 */
	const handleExtractChapters = async () => {
		setIsExtracting(true);
		setLoading("extract-chapters", true);

		try {
			const _result = await extractBookChapters(book.id);
			const chapters = await getBookChapters(book.id);
			setApiChapters(chapters || []);
		} catch (_error) {
			console.error("Failed to extract chapters:", _error);
		} finally {
			setIsExtracting(false);
			setLoading("extract-chapters", false);
		}
	};

	/**
	 * Check if current page is in chapter
	 */
	const isPageInChapter = useCallback(
		(chapter) => {
			if (chapter.startPage && chapter.endPage) {
				return (
					currentPage >= chapter.startPage && currentPage <= chapter.endPage
				);
			}
			if (chapter.page) {
				return currentPage === chapter.page;
			}
			if (chapter.children?.length > 0) {
				return chapter.children.some((section) => {
					if (section.startPage && section.endPage) {
						return (
							currentPage >= section.startPage && currentPage <= section.endPage
						);
					}
					return currentPage === section.page;
				});
			}
			return false;
		},
		[currentPage],
	);

	/**
	 * Toggle chapter expansion
	 */
	const handleToggleChapter = (chapterIndex) => {
		setExpandedChapters((prev) =>
			prev.includes(chapterIndex)
				? prev.filter((idx) => idx !== chapterIndex)
				: [...prev, chapterIndex],
		);
	};

	// Auto-expand chapter containing current page
	useEffect(() => {
		const chapters = book?.tableOfContents || apiChapters;
		if (chapters.length > 0 && currentPage) {
			const currentChapterIndex = chapters.findIndex((chapter) => {
				// Inline isPageInChapter logic to avoid function dependency
				if (chapter.startPage && chapter.endPage) {
					return (
						currentPage >= chapter.startPage && currentPage <= chapter.endPage
					);
				}
				if (chapter.page) {
					return currentPage === chapter.page;
				}
				if (chapter.children?.length > 0) {
					return chapter.children.some((section) => {
						if (section.startPage && section.endPage) {
							return (
								currentPage >= section.startPage &&
								currentPage <= section.endPage
							);
						}
						return currentPage === section.page;
					});
				}
				return false;
			});

			// Only expand if not already expanded to avoid infinite loops
			setExpandedChapters((prev) => {
				if (currentChapterIndex >= 0 && !prev.includes(currentChapterIndex)) {
					return [...prev, currentChapterIndex];
				}
				return prev;
			});
		}
	}, [currentPage, book?.tableOfContents, apiChapters]);

	if (!book) return null;

	const chapters =
		book.tableOfContents?.length > 0 ? book.tableOfContents : apiChapters;

	const overallProgress =
		stats.percentage > 0 ? stats.percentage : progressPercentage;

	// Empty state
	if (!chapters.length) {
		return (
			<SidebarContainer>
				<div className="px-4 pt-20 pb-4">
					<div className="text-center text-zinc-500 text-sm mt-8">
						<FileText className="w-12 h-12 mx-auto mb-4 text-zinc-300" />
						<p>No table of contents available</p>
						<p className="text-xs mt-2">
							This book doesn't have chapter information.
						</p>
						<button
							type="button"
							onClick={handleExtractChapters}
							disabled={isExtracting}
							className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
						>
							<FileText className="w-4 h-4" />
							{isExtracting ? "Extracting..." : "Extract Chapters"}
						</button>
					</div>
				</div>
			</SidebarContainer>
		);
	}

	return (
		<SidebarContainer>
			<ProgressIndicator
				progress={overallProgress}
				variant="book"
				suffix="Read"
			>
				<span className="text-xs text-zinc-500">
					{currentPage && book.totalPages
						? `Page ${currentPage} of ${book.totalPages}`
						: "Loading..."}
				</span>
			</ProgressIndicator>

			<SidebarNav>
				{chapters.map((chapter, chapterIndex) => {
					const isExpanded = expandedChapters.includes(chapterIndex);
					const chapterProgress = getChapterProgress(chapter);
					const isActive = isPageInChapter(chapter);
					const hasChildren = chapter.children?.length > 0;
					const isCompleted = chapterProgress === 100;

					// For chapters without children, show checkbox
					if (!hasChildren) {
						return (
							<div
								key={`chapter_${chapterIndex}_${chapter.id}`}
								className={`rounded-2xl border ${
									isActive
										? "border-blue-200 bg-blue-50/50"
										: "border-border bg-white"
								} shadow-sm overflow-hidden`}
							>
								<div
									className="flex items-center gap-3 justify-between w-full px-4 py-3 text-left cursor-pointer hover:bg-zinc-50/50 transition-colors"
									onClick={(e) => {
										// Only navigate if we didn't click on the checkbox
										if (!e.target.closest("button")) {
											onChapterClick?.(
												chapter.page || chapter.startPage,
												chapter.id,
											);
										}
									}}
								>
									<div className="flex items-center gap-3 flex-1 min-w-0">
										<ProgressCircle
											number={chapterIndex + 1}
											progress={chapterProgress}
											variant="book"
										/>
										<CompletionCheckbox
											isCompleted={isCompleted}
											onClick={(e) => {
												e.stopPropagation();
												toggleSectionCompletion(chapter);
											}}
											variant="book"
										/>
										<span className="line-clamp-2 text-sm font-semibold">
											{chapter.title}
										</span>
									</div>
								</div>
							</div>
						);
					}

					// For chapters with children
					return (
						<ExpandableSection
							key={`chapter_${chapterIndex}_${chapter.id}`}
							title={chapter.title}
							isExpanded={isExpanded}
							onToggle={() => handleToggleChapter(chapterIndex)}
							isActive={isActive}
							showExpandButton={true}
							variant="book"
							headerContent={
								<div
									onClick={(e) => {
										e.stopPropagation();
										toggleSectionCompletion(chapter);
									}}
									className="hover:scale-110 transition-transform cursor-pointer"
									role="button"
									tabIndex={0}
									onKeyDown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											e.preventDefault();
											e.stopPropagation();
											toggleSectionCompletion(chapter);
										}
									}}
									aria-label={`Toggle completion for ${chapter.title}`}
								>
									<ProgressCircle
										number={chapterIndex + 1}
										progress={chapterProgress}
										variant="book"
									/>
								</div>
							}
						>
							<ol>
								{chapter.children.map((section, sectionIndex) => {
									const isSectionCompleted = tocProgressUtils.isCompleted(
										section.id,
									);
									const isSectionActive =
										currentPage === section.page ||
										(section.startPage &&
											section.endPage &&
											currentPage >= section.startPage &&
											currentPage <= section.endPage);

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
													isCompleted={isSectionCompleted}
													onClick={(e) => {
														e.stopPropagation();
														toggleSectionCompletion(section);
													}}
													variant="book"
												/>
											}
										/>
									);
								})}
							</ol>
						</ExpandableSection>
					);
				})}
			</SidebarNav>
		</SidebarContainer>
	);
}

export default BookSidebar;
