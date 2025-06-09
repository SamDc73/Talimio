import { useToast } from "@/hooks/use-toast";
import {
	getCompletedSections,
	saveBookProgressStats,
	updateBookProgress,
} from "@/services/bookProgressService";
import {
	extractBookChapters,
	getBookChapters,
	updateChapterStatus,
} from "@/services/booksService";
import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import CompletionCheckbox from "./CompletionCheckbox";
import ExpandableSection from "./ExpandableSection";
import ProgressCircle from "./ProgressCircle";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarItem from "./SidebarItem";
import SidebarNav from "./SidebarNav";

function BookSidebar({ book, currentPage = 1, onChapterClick }) {
	const [expandedChapters, setExpandedChapters] = useState([0]);
	const [completedSections, setCompletedSections] = useState(new Set());
	const [apiChapters, setApiChapters] = useState([]);
	const [isLoadingChapters, setIsLoadingChapters] = useState(false);
	const [isExtracting, setIsExtracting] = useState(false);
	const { toast } = useToast();

	// Fetch chapters from API and load progress
	useEffect(() => {
		if (!book?.id) return;

		async function fetchChapters() {
			setIsLoadingChapters(true);
			try {
				const chapters = await getBookChapters(book.id);
				setApiChapters(chapters || []);

				// Load progress from both API chapters and localStorage
				const completed = new Set();

				// If we have API chapters, use their status
				if (chapters && chapters.length > 0) {
					for (const chapter of chapters) {
						if (chapter.status === "completed") {
							completed.add(chapter.id);
						}
					}
				}

				// Load tableOfContents progress from localStorage
				const tocCompleted = getCompletedSections(book.id);
				for (const id of tocCompleted) {
					completed.add(id);
				}

				setCompletedSections(completed);
			} catch (error) {
				console.error("Failed to fetch chapters:", error);
				// Fall back to table of contents if API fails
				setApiChapters([]);

				// Still load ToC progress from localStorage
				const tocCompleted = getCompletedSections(book.id);
				setCompletedSections(tocCompleted);
			} finally {
				setIsLoadingChapters(false);
			}
		}

		fetchChapters();
	}, [book?.id]);

	const handleExtractChapters = async () => {
		setIsExtracting(true);
		try {
			const result = await extractBookChapters(book.id);
			toast({
				title: "Chapters extracted",
				description: `Successfully extracted ${result.count || 0} chapters`,
			});

			// Refresh chapters
			const chapters = await getBookChapters(book.id);
			setApiChapters(chapters || []);
		} catch (error) {
			toast({
				title: "Error",
				description: "Failed to extract chapters",
				variant: "destructive",
			});
		} finally {
			setIsExtracting(false);
		}
	};

	if (!book) return null;

	// Prefer tableOfContents (hierarchical with children) over API chapters (flat)
	// Only use API chapters if no tableOfContents exists
	const hasTableOfContents =
		book.tableOfContents && book.tableOfContents.length > 0;
	const chapters = hasTableOfContents ? book.tableOfContents : apiChapters;

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

						{/* Extract chapters button */}
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

	const handleToggleChapter = (chapterIndex) => {
		setExpandedChapters((prev) =>
			prev.includes(chapterIndex)
				? prev.filter((idx) => idx !== chapterIndex)
				: [...prev, chapterIndex],
		);
	};

	const handleSectionClick = async (section, pageNumber) => {
		const sectionId = section.id || section.chapter_id;
		const isCompleted = completedSections.has(sectionId);
		const newStatus = isCompleted ? "not_started" : "completed";

		// Optimistic update
		const newCompletedSections = new Set(completedSections);
		if (isCompleted) {
			newCompletedSections.delete(sectionId);
		} else {
			newCompletedSections.add(sectionId);
		}
		setCompletedSections(newCompletedSections);

		// Save progress based on data source
		const usingTableOfContents = hasTableOfContents;

		if (usingTableOfContents) {
			// Save tableOfContents progress using service
			updateBookProgress(book.id, sectionId, !isCompleted);

			// Update stats with properly calculated count
			// We need to calculate based on chapters structure, not just set size
			const tempCompletedSections = newCompletedSections;
			const calculateNewCompletedCount = () => {
				let count = 0;
				for (const ch of chapters) {
					if (ch.children && ch.children.length > 0) {
						for (const section of ch.children) {
							if (tempCompletedSections.has(section.id)) {
								count++;
							}
						}
					} else {
						if (tempCompletedSections.has(ch.id)) {
							count++;
						}
					}
				}
				return count;
			};

			const newCompletedCount = calculateNewCompletedCount();
			saveBookProgressStats(book.id, totalSections, newCompletedCount);

			toast({
				title: "Progress saved",
				description: `Section marked as ${newStatus.replace("_", " ")}`,
			});
		} else if (apiChapters.length > 0 && section.chapter_id) {
			// Update via API for API chapters
			try {
				await updateChapterStatus(book.id, section.chapter_id, newStatus);
				toast({
					title: "Chapter updated",
					description: `Chapter marked as ${newStatus.replace("_", " ")}`,
				});
			} catch (error) {
				// Revert optimistic update
				setCompletedSections(completedSections);

				toast({
					title: "Error",
					description: "Failed to update chapter status",
					variant: "destructive",
				});
			}
		}

		if (onChapterClick) {
			onChapterClick(pageNumber);
		}
	};

	const getChapterProgress = (chapter) => {
		if (!chapter.children || chapter.children.length === 0) return 0;
		const completedCount = chapter.children.filter((s) =>
			completedSections.has(s.id),
		).length;
		return (completedCount / chapter.children.length) * 100;
	};

	const isPageInRange = (page, chapter) => {
		if (chapter.startPage && chapter.endPage) {
			return page >= chapter.startPage && page <= chapter.endPage;
		}
		return page === chapter.page;
	};

	const countAllSections = (chapters) => {
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

	// Count completed sections with SAME logic as countAllSections
	const countCompletedSectionsForChapters = (chapters) => {
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

	const totalSections = countAllSections(chapters);
	const completedCount = countCompletedSectionsForChapters(chapters);
	const overallProgress =
		totalSections > 0 ? Math.round((completedCount / totalSections) * 100) : 0;

	// Save stats for home page when we have table of contents
	useEffect(() => {
		if (hasTableOfContents && totalSections > 0) {
			saveBookProgressStats(book.id, totalSections, completedCount);
		}
	}, [book.id, hasTableOfContents, totalSections, completedCount]);

	return (
		<SidebarContainer>
			<ProgressIndicator progress={overallProgress} suffix="Read">
				<span className="text-xs text-zinc-500">
					Page {currentPage} of {book.totalPages || "?"}
				</span>
			</ProgressIndicator>

			<SidebarNav>
				<h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-2">
					Table of Contents
				</h4>

				{chapters.map((chapter, chapterIndex) => {
					const isExpanded = expandedChapters.includes(chapterIndex);
					const chapterProgress = getChapterProgress(chapter);
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
							headerContent={
								<button
									type="button"
									onClick={(e) => {
										e.stopPropagation();
										if (onChapterClick) {
											onChapterClick(chapter.page || chapter.startPage);
										}
									}}
									className="cursor-pointer hover:text-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded bg-transparent border-none p-0"
								>
									<ProgressCircle
										number={chapterIndex + 1}
										progress={chapterProgress}
									/>
								</button>
							}
						>
							{chapter.children && chapter.children.length > 0 && (
								<ol>
									{chapter.children.map((section, sectionIndex) => {
										const isCompleted = completedSections.has(section.id);
										const isCurrentSection = currentPage === section.page;

										return (
											<SidebarItem
												key={`${chapter.id}_${sectionIndex}_${section.id}`}
												title={
													<>
														<span className="line-clamp-2 text-sm">
															{section.title}
														</span>
														<span className="text-xs text-zinc-500 ml-2">
															p. {section.page}
														</span>
													</>
												}
												isActive={isCurrentSection}
												isCompleted={isCompleted}
												onClick={() =>
													handleSectionClick(section, section.page)
												}
												leftContent={
													<CompletionCheckbox
														isCompleted={isCompleted}
														onClick={() =>
															handleSectionClick(section, section.page)
														}
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
				<div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden mt-6">
					<div className="px-4 py-3 border-b border-zinc-100">
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

export default BookSidebar;
