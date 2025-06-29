import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { BookHeader } from "@/components/header/BookHeader";
import BookSidebar from "@/components/sidebar/BookSidebar";
import { booksApi } from "@/services/booksApi";
import {
	initializeTocProgress,
	markChapterInProgress,
	migrateFromLocalStorage,
} from "@/services/tocProgressService";
import useAppStore from "@/stores/useAppStore";
import EPUBViewer from "./components/EPUBViewer";
import PDFViewer from "./components/PDFViewer";
import "./BookViewer.css";

// Stable empty object references to prevent infinite re-renders
const EMPTY_OBJECT = {};
const EMPTY_PROGRESS_STATS = {
	totalSections: 0,
	completedSections: 0,
	percentage: 0,
	type: "unknown",
};

/**
 * Enhanced Book Viewer using Zustand for state management
 * Replaces multiple custom hooks with unified store
 */
const BookViewerContent = () => {
	const { bookId } = useParams();
	const [book, setBook] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const pdfViewerRef = useRef(null);
	const isOpen = useAppStore((state) => state.preferences.sidebarOpen);
	const toggle = useAppStore((state) => state.toggleSidebar);
	// Zustand store selectors - use stable references
	const bookProgress = useAppStore((state) => state.books.progress[bookId]);
	const updateBookProgress = useAppStore((state) => state.updateBookProgress);
	const updateChapterStatus = useAppStore(
		(state) => state.updateBookChapterStatus,
	);
	const appSetLoading = useAppStore((state) => state.setLoading);
	const addError = useAppStore((state) => state.addError);
	// ToC progress selectors - use stable references
	const tocProgress = useAppStore(
		(state) => state.books.tocProgress[bookId] || EMPTY_OBJECT,
	);
	const progressStats = useAppStore(
		(state) => state.books.progressStats[bookId] || EMPTY_PROGRESS_STATS,
	);

	// Use useMemo for computed completedSections to avoid new Set on every render
	const completedSections = useMemo(() => {
		const progress = tocProgress;
		return new Set(
			Object.entries(progress)
				.filter(([_, completed]) => completed)
				.map(([sectionId, _]) => sectionId),
		);
	}, [tocProgress]);
	// Local state derived from store - avoid defaulting to 1 to prevent flickering
	const [currentPage, setCurrentPage] = useState(() => {
		// Only set initial page if we have valid bookProgress data
		return bookProgress?.currentPage || null;
	});
	const [totalPages, setTotalPages] = useState(bookProgress?.totalPages || 0);
	const [zoomLevel, setZoomLevel] = useState(bookProgress?.zoomLevel || 100);
	// Chapter completion from store - use stable reference
	const chapterCompletion = useAppStore(
		(state) => state.books.chapterCompletion[bookId] || EMPTY_OBJECT,
	);
	// Update local state when bookProgress changes
	useEffect(() => {
		if (bookProgress) {
			// Only update if we have a valid current page from store
			if (bookProgress.currentPage) {
				setCurrentPage(bookProgress.currentPage);
			}
			setTotalPages(bookProgress.totalPages || 0);
			setZoomLevel(bookProgress.zoomLevel || 100);
		}
	}, [bookProgress]);
	/**
	 * Load book data and initialize progress
	 */
	useEffect(() => {
		const fetchBook = async () => {
			try {
				setLoading(true);
				appSetLoading("book-fetch", true);

				const data = await booksApi.getBook(bookId);
				console.log("Book loaded:", data);
				setBook(data);

				const bookTotalPages = data.totalPages || 0;
				setTotalPages(bookTotalPages);

				// Initialize ToC progress system
				initializeTocProgress(bookId, data);

				// Migrate from old localStorage if needed
				migrateFromLocalStorage(bookId);

				// Get smart initial page (localStorage priority over server)
				const serverCurrentPage =
					data.progress?.currentPage || data.currentPage || 1;
				const localProgress = useAppStore.getState().getBookProgress(bookId);

				// Use local progress if more recent, otherwise use server
				const initialPage =
					localProgress.lastUpdated &&
					(!data.progress?.lastUpdated ||
						localProgress.lastUpdated >
							new Date(data.progress.lastUpdated).getTime())
						? localProgress.currentPage
						: serverCurrentPage;

				// Set initial page immediately to prevent flickering
				setCurrentPage(initialPage);

				// Update store with initial data if needed (skip sync during init)
				if (
					!localProgress.totalPages ||
					localProgress.totalPages !== bookTotalPages
				) {
					updateBookProgress(
						bookId,
						{
							totalPages: bookTotalPages,
							currentPage: initialPage,
						},
						true,
					); // Skip sync during initialization
				}
			} catch (err) {
				setError(err.message);
				addError(`Failed to load book: ${err.message}`);
			} finally {
				setLoading(false);
				appSetLoading("book-fetch", false);
			}
		};
		if (bookId) {
			fetchBook();
		}
	}, [bookId, appSetLoading, addError, updateBookProgress]); // Now stable dependencies

	/**
	 * Initialize chapter statuses from book table of contents
	 */
	useEffect(() => {
		if (!book?.tableOfContents) return;

		try {
			const toc =
				typeof book.tableOfContents === "string"
					? JSON.parse(book.tableOfContents)
					: book.tableOfContents;

			const initializeChapterStatus = (items) => {
				for (const item of items) {
					if (item.level === 0 && !chapterCompletion[item.id]) {
						// Initialize chapter as not started if not already tracked
						updateChapterStatus(bookId, item.id, false);
					}
					if (item.children) {
						initializeChapterStatus(item.children);
					}
				}
			};

			initializeChapterStatus(toc);
		} catch (error) {
			console.warn("Failed to initialize chapter statuses:", error);
		}
	}, [book?.tableOfContents, bookId, chapterCompletion, updateChapterStatus]); // Now stable dependencies

	/**
	 * Handle page changes with chapter detection
	 */
	const handlePageChange = useCallback(
		(pageNum) => {
			setCurrentPage(pageNum);

			// Update store with new page
			updateBookProgress(bookId, {
				currentPage: pageNum,
				lastAccessed: Date.now(),
			});

			// Auto-mark chapters as in-progress when entering their page range
			if (book?.tableOfContents) {
				try {
					const toc =
						typeof book.tableOfContents === "string"
							? JSON.parse(book.tableOfContents)
							: book.tableOfContents;

					// Use new ToC progress system
					markChapterInProgress(bookId, pageNum, toc);
				} catch (error) {
					console.warn("Failed to check chapter entry:", error);
				}
			}
		},
		[bookId, book?.tableOfContents, updateBookProgress],
	); // Now stable dependencies

	/**
	 * Handle zoom changes
	 */
	const handleZoomChange = useCallback(
		(newZoom) => {
			setZoomLevel(newZoom);
			updateBookProgress(bookId, { zoomLevel: newZoom });
		},
		[bookId, updateBookProgress],
	); // Now stable dependencies

	/**
	 * Zoom controls
	 */
	const handleZoomIn = useCallback(() => {
		const newZoom = Math.min(zoomLevel + 20, 300);
		handleZoomChange(newZoom);
	}, [zoomLevel, handleZoomChange]);
	const handleZoomOut = useCallback(() => {
		const newZoom = Math.max(zoomLevel - 20, 50);
		handleZoomChange(newZoom);
	}, [zoomLevel, handleZoomChange]);
	const handleFitToScreen = useCallback(() => {
		if (pdfViewerRef.current?.calculateFitToWidth) {
			pdfViewerRef.current.calculateFitToWidth();
		}
	}, []);

	/**
	 * Chapter click handler for sidebar
	 */
	const handleChapterClick = useCallback(
		(pageNumber, chapterId) => {
			const fileType = book?.fileType?.toLowerCase();

			// Navigate to page
			if (fileType === "pdf" && pdfViewerRef.current) {
				pdfViewerRef.current.scrollToPage?.(pageNumber);
			}

			// Mark chapter as in-progress if not already completed
			if (chapterId && !chapterCompletion[chapterId]) {
				updateChapterStatus(bookId, chapterId, true);
			}
		},
		[book?.fileType, bookId, chapterCompletion, updateChapterStatus],
	); // Now stable dependencies

	// Use the reliable, calculated percentage from the store
	const progressPercentage = progressStats.percentage || 0;

	/**
	 * Save progress on page unload using beacon API
	 */
	useEffect(() => {
		const saveProgressOnUnload = () => {
			if (currentPage > 1 && book && totalPages) {
				const progressData = {
					currentPage,
					progressPercentage,
					status: progressPercentage >= 100 ? "completed" : "reading",
				};

				// Use beacon API for reliable delivery
				navigator.sendBeacon(
					`/api/v1/books/${bookId}/progress`,
					new Blob([JSON.stringify(progressData)], {
						type: "application/json",
					}),
				);
			}
		};

		const handleBeforeUnload = () => {
			saveProgressOnUnload();
		};

		window.addEventListener("beforeunload", handleBeforeUnload);

		return () => {
			window.removeEventListener("beforeunload", handleBeforeUnload);
			// Also save progress when component unmounts
			saveProgressOnUnload();
		};
	}, [currentPage, book, totalPages, bookId, progressPercentage]);
	/**
	 * Render loading state
	 */
	if (loading) {
		return (
			<div className="book-viewer-loading">
				<div className="spinner">Loading book...</div>
			</div>
		);
	}

	/**
	 * Render error state
	 */
	if (error) {
		return (
			<div className="book-viewer-error">
				<h2>Error loading book</h2>
				<p>{error}</p>
			</div>
		);
	}

	/**
	 * Render not found state
	 */
	if (!book) {
		return (
			<div className="book-viewer-error">
				<h2>Book not found</h2>
			</div>
		);
	}

	const fileType = book.fileType?.toLowerCase();
	const bookUrl = `/api/v1/books/${bookId}/file`;

	return (
		<div className="flex h-screen bg-background">
			<BookHeader
				bookTitle={book.title}
				bookAuthor={book.author}
				currentPage={currentPage}
				totalPages={totalPages}
				progressPercentage={progressPercentage}
				isOpen={isOpen}
				toggleSidebar={toggle}
				onZoomIn={handleZoomIn}
				onZoomOut={handleZoomOut}
				onFitToScreen={handleFitToScreen}
				zoomLevel={zoomLevel}
				showZoomControls={fileType === "pdf"}
			/>

			<BookSidebar
				book={book}
				currentPage={currentPage}
				chapterCompletion={chapterCompletion}
				onChapterClick={handleChapterClick}
				progressPercentage={progressPercentage}
				tocProgress={tocProgress}
				progressStats={progressStats}
				completedSections={completedSections}
			/>

			<main
				className={`flex-1 transition-all duration-300 ${isOpen ? "ml-64" : "ml-0"} pt-16`}
			>
				<div className="book-viewer-container h-full">
					{fileType === "pdf" ? (
						<PDFViewer
							ref={pdfViewerRef}
							url={bookUrl}
							bookInfo={book}
							onPageChange={handlePageChange}
							zoom={zoomLevel}
							onZoomChange={handleZoomChange}
							initialPage={currentPage}
						/>
					) : fileType === "epub" ? (
						<EPUBViewer
							url={bookUrl}
							bookInfo={book}
							onLocationChange={(location) => {
								// Handle EPUB location changes
								if (location.currentPage) {
									handlePageChange(location.currentPage);
								}
							}}
						/>
					) : (
						<div className="book-viewer-error">
							<h2>Unsupported file format</h2>
							<p>Only PDF and EPUB files are supported.</p>
						</div>
					)}
				</div>
			</main>
		</div>
	);
};

/**
 * Main BookViewer component
 */
const BookViewer = BookViewerContent;

export default BookViewer;
