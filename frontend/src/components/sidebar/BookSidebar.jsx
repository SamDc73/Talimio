import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
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

/**
 * Enhanced BookSidebar using Zustand for state management
 * Replaces hybrid tracker and localStorage with unified store
 */
function BookSidebarV2({
	book,
	currentPage = 1,
	onChapterClick,
	chapterCompletion = {},
	progressPercentage = 0,
	tocProgress = {},
	progressStats = {},
	completedSections = new Set(),
}) {
	const [expandedChapters, setExpandedChapters] = useState([0]);
	const [apiChapters, setApiChapters] = useState([]);
	const [_isLoadingChapters, setIsLoadingChapters] = useState(false);
	const [isExtracting, setIsExtracting] = useState(false);
	const { toast } = useToast();

	// Zustand store actions
	const updateChapterStatus = useAppStore(
		(state) => state.updateBookChapterStatus,
	);
	const setLoading = useAppStore((state) => state.setLoading);

	// Use enhanced ToC progress hook
	const tocProgressUtils = useTocProgress(book?.id);

	/**
	 * Fetch chapters from API
	 */
	useEffect(() => {
		if (!book?.id) return;

		async function fetchChapters() {
			setIsLoadingChapters(true);
			setLoading("book-chapters", true);

			try {
				const chapters = await getBookChapters(book.id);
				setApiChapters(chapters || []);

				// Initialize chapter statuses in store if they don't exist
				if (chapters && chapters.length > 0) {
					for (const chapter of chapters) {
						if (chapterCompletion[chapter.id] === undefined) {
							updateChapterStatus(
								book.id,
								chapter.id,
								chapter.status === "completed",
							);
						}
					}
				}
			} catch (error) {
				console.error("Failed to fetch chapters:", error);
				setApiChapters([]);
			} finally {
				setIsLoadingChapters(false);
				setLoading("book-chapters", false);
			}
		}

		fetchChapters();
	}, [book?.id, updateChapterStatus, setLoading, chapterCompletion]);

	/**
	 * Extract chapters using AI
	 */
	const handleExtractChapters = async () => {
		setIsExtracting(true);
		setLoading("extract-chapters", true);

		try {
			const result = await extractBookChapters(book.id);
			toast({
				title: "Chapters extracted",
				description: `Successfully extracted ${result.count || 0} chapters`,
			});

			// Refresh chapters
			const chapters = await getBookChapters(book.id);
			setApiChapters(chapters || []);
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to extract chapters",
				variant: "destructive",
			});
		} finally {
			setIsExtracting(false);
			setLoading("extract-chapters", false);
		}
	};

	if (!book) return null;

	// Prefer tableOfContents (hierarchical) over API chapters (flat)
	const hasTableOfContents =
		book.tableOfContents && book.tableOfContents.length > 0;
	const chapters = hasTableOfContents ? book.tableOfContents : apiChapters;

	/**
	 * Render empty state
	 */
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
							className="mt-4 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mx-auto"
						>
							<Download className="w-4 h-4" />
							{isExtracting ? "Extracting..." : "Extract Chapters"}
						</button>
					</div>
				</div>
			</SidebarContainer>
		);
	}

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

	/**
	 * Handle section/chapter click - navigates to the page
	 */
	const handleSectionClick = async (section, pageNumber) => {
		// Navigate to chapter/section
		if (onChapterClick) {
			onChapterClick(pageNumber, section.id || section.chapter_id);
		}
	};

	/**
	 * Handle completion toggle without navigation
	 */
	const handleCompletionToggle = async (section) => {
		const sectionId = section.id || section.chapter_id;
		const isCompleted = tocProgressUtils.isCompleted(sectionId);
		const newStatus = !isCompleted;

		// Update ToC progress using the enhanced system
		tocProgressUtils.updateSection(sectionId, newStatus);

		toast({
			title: "Progress updated",
			description: `Section marked as ${newStatus ? "completed" : "not started"}`,
		});
	};

	/**
	 * Calculate progress for a chapter based on completed children
	 */
	const getChapterProgressPercentage = (chapter) => {
		return tocProgressUtils.getChapterProgress(chapter);
	};

	/**
	 * Check if current page is in chapter range
	 */
	const isPageInRange = (page, chapter) => {
		// If chapter has start and end page, check if current page is within range
		if (chapter.startPage && chapter.endPage) {
			return page >= chapter.startPage && page <= chapter.endPage;
		}
		// If chapter has only one page, check exact match
		if (chapter.page) {
			return page === chapter.page;
		}
		// If chapter has children (sections), check if any section contains the current page
		if (chapter.children && chapter.children.length > 0) {
			return chapter.children.some((section) => {
				if (section.startPage && section.endPage) {
					return page >= section.startPage && page <= section.endPage;
				}
				return page === section.page;
			});
		}
		return false;
	};

	// Auto-expand chapter containing current page
	useEffect(() => {
		if (chapters.length > 0 && currentPage) {
			const currentChapterIndex = chapters.findIndex((chapter) =>
				isPageInRange(currentPage, chapter),
			);
			if (
				currentChapterIndex >= 0 &&
				!expandedChapters.includes(currentChapterIndex)
			) {
				setExpandedChapters((prev) => [...prev, currentChapterIndex]);
			}
		}
	}, [currentPage, chapters, expandedChapters, isPageInRange]);

	/**
	 * Count all sections/chapters for progress calculation
	 */
	const _countAllSections = (chapters) => {
		let count = 0;
		for (const ch of chapters) {
			if (ch.children && ch.children.length > 0) {
				count += ch.children.length;
			} else {
				count += 1;
			}
		}
		return count;
	};

	/**
	 * Count completed sections matching the same logic
	 */
	const _countCompletedSections = (chapters) => {
		let count = 0;
		for (const ch of chapters) {
			if (ch.children && ch.children.length > 0) {
				// Count completed children
				for (const section of ch.children) {
					if (completedSections.has(section.id)) {
						count++;
					}
				}
			} else {
				// Chapter is a section itself
				if (completedSections.has(ch.id)) {
					count++;
				}
			}
		}
		return count;
	};

	// Use enhanced progress stats from store
	const stats = tocProgressUtils.progressStats;
	const overallProgress =
		stats.percentage > 0 ? stats.percentage : progressPercentage; // Fall back to page-based progress

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
				<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">
					Table of Contents
				</h4>

				{chapters.map((chapter, chapterIndex) => {
					const isExpanded = expandedChapters.includes(chapterIndex);
					const chapterProgress = getChapterProgressPercentage(chapter);
					const isCurrentChapter = isPageInRange(currentPage, chapter);
					const hasChildren = chapter.children && chapter.children.length > 0;

					return (
						<ExpandableSection
							key={`chapter_${chapterIndex}_${chapter.id}`}
							title={chapter.title}
							isExpanded={isExpanded}
							onToggle={() => handleToggleChapter(chapterIndex)}
							isActive={isCurrentChapter}
							showExpandButton={hasChildren}
							variant="book"
							headerContent={
								<button
									type="button"
									onClick={(e) => {
										e.stopPropagation();
										if (onChapterClick) {
											onChapterClick(
												chapter.page || chapter.startPage,
												chapter.id,
											);
										}
									}}
									className="cursor-pointer hover:text-blue-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 rounded bg-transparent border-none p-0"
								>
									<ProgressCircle
										number={chapterIndex + 1}
										progress={chapterProgress}
										variant="book"
									/>
								</button>
							}
						>
							{chapter.children && chapter.children.length > 0 && (
								<ol>
									{chapter.children.map((section, sectionIndex) => {
										const isCompleted = tocProgressUtils.isCompleted(
											section.id,
										);
										// Better section detection: check if current page is within section range
										const isCurrentSection = (() => {
											if (section.startPage && section.endPage) {
												return (
													currentPage >= section.startPage &&
													currentPage <= section.endPage
												);
											}
											return currentPage === section.page;
										})();

										return (
											<SidebarItem
												key={`${chapter.id}_${sectionIndex}_${section.id}`}
												title={
													<>
														<span className="line-clamp-2 text-sm">
															{section.title}
														</span>
														<span className="text-xs text-blue-500 ml-2">
															p. {section.page}
														</span>
													</>
												}
												isActive={isCurrentSection}
												isCompleted={isCompleted}
												onClick={() =>
													handleSectionClick(section, section.page)
												}
												variant="book"
												leftContent={
													<CompletionCheckbox
														isCompleted={isCompleted}
														onClick={(e) => {
															e.stopPropagation();
															handleCompletionToggle(section);
														}}
														variant="book"
													/>
												}
											/>
										);
									})}
								</ol>
							)}
						</ExpandableSection>
					);
				})}

				{/* Book metadata section */}
				<div className="rounded-2xl border border-border bg-white shadow-sm overflow-hidden mt-6">
					<div className="px-4 py-3 border-b border-border">
						<h4 className="font-semibold text-sm text-zinc-900 flex items-center gap-2">
							<FileText className="w-4 h-4" />
							Book Details
						</h4>
					</div>
					<div className="px-4 py-3 space-y-2 text-sm">
						<div className="flex justify-between">
							<span className="text-zinc-600">Pages</span>
							<span className="text-zinc-900">
								{book.totalPages || "Unknown"}
							</span>
						</div>
						<div className="flex justify-between">
							<span className="text-zinc-600">Progress</span>
							<span className="text-zinc-900">{overallProgress}%</span>
						</div>
						{stats.totalSections > 0 && (
							<div className="flex justify-between">
								<span className="text-zinc-600">Sections</span>
								<span className="text-zinc-900">
									{stats.completedSections}/{stats.totalSections}
								</span>
							</div>
						)}
						{book.publicationYear && (
							<div className="flex justify-between">
								<span className="text-zinc-600">Published</span>
								<span className="text-zinc-900">{book.publicationYear}</span>
							</div>
						)}
						{book.language && (
							<div className="flex justify-between">
								<span className="text-zinc-600">Language</span>
								<span className="text-zinc-900">{book.language}</span>
							</div>
						)}
						{book.isbn && (
							<div className="flex justify-between">
								<span className="text-zinc-600">ISBN</span>
								<span className="text-zinc-900 text-xs">{book.isbn}</span>
							</div>
						)}
					</div>
				</div>
			</SidebarNav>
		</SidebarContainer>
	);
}

export default BookSidebarV2;
