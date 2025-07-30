import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { BookHeader } from "@/components/header/BookHeader";
import BookSidebar from "@/components/sidebar/BookSidebar";
import { booksApi } from "@/services/booksApi";
import useAppStore from "@/stores/useAppStore";
import EPUBViewer from "./components/EPUBViewer";
import PDFErrorBoundary from "./components/PDFErrorBoundary";
import PDFViewer from "./components/PDFViewer";
import "./BookViewer.css";

// Remove render tracking in production
const trackRender = () => {};

const BookViewerContent = () => {
	trackRender("BookViewerContent");
	const { bookId } = useParams();
	const [book, setBook] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const pdfViewerRef = useRef(null);

	// Temporarily disabled page tracking to test basic PDF rendering
	// const [currentPage, setCurrentPage] = useState(null);
	// const currentPageRef = useRef(null);

	// Create a mock bookProgress object to keep the component working
	const _bookProgress = {
		progress: { percentage: 0 },
		updateProgress: () => {},
	};

	// Temporarily disabled store sync to test basic PDF rendering
	// const updateBookReadingStateRef = useRef();
	// const setBookZoomRef = useRef();

	// useEffect(() => {
	// 	const state = useAppStore.getState();
	// 	updateBookReadingStateRef.current = state.updateBookReadingState;
	// 	setBookZoomRef.current = state.setBookZoom;
	// }, []);

	// Simple local zoom state - no store sync for now
	const [zoom, setZoom] = useState(100);

	// Sidebar state management - use refs to avoid re-renders
	const toggleSidebarRef = useRef();
	const [sidebarOpen, setSidebarOpen] = useState(() => {
		// Initialize from store once
		return useAppStore.getState().preferences?.sidebarOpen ?? true;
	});

	// Subscribe to sidebar changes only
	useEffect(() => {
		const state = useAppStore.getState();
		toggleSidebarRef.current = state.toggleSidebar;

		// Subscribe to sidebar state changes only
		const unsubscribe = useAppStore.subscribe((newState, prevState) => {
			const newSidebarOpen = newState.preferences?.sidebarOpen ?? true;
			const prevSidebarOpen = prevState?.preferences?.sidebarOpen ?? true;

			if (newSidebarOpen !== prevSidebarOpen) {
				setSidebarOpen(newSidebarOpen);
			}
		});

		return unsubscribe;
	}, []);

	// Memoize the book URL to prevent react-pdf from re-fetching on every render
	// Must be before any conditional returns to follow React hooks rules
	const bookUrl = useMemo(() => `/api/v1/books/${bookId}/file`, [bookId]);

	useEffect(() => {
		const fetchBook = async () => {
			try {
				setLoading(true);
				const data = await booksApi.getBook(bookId);
				setBook(data);

				// Page tracking disabled for testing
				// if (currentPage === null) {
				// 	// Page setting logic disabled
				// }
			} catch (err) {
				setError(err.message);
			} finally {
				setLoading(false);
			}
		};
		if (bookId) {
			fetchBook();
		}
	}, [bookId]); // Only depend on bookId

	// Temporarily disabled page change handling
	// const pageChangeTimeoutRef = useRef(null);
	// const handlePageChange = useCallback((page) => {
	// 	// Page change logic disabled for testing
	// }, [bookId]);

	// Extract stable values from book object
	const _totalPages = book?.totalPages || book?.total_pages || 0;

	// Simple zoom handlers - no store sync for now
	const handleZoomIn = useCallback(() => {
		setZoom((currentZoom) => Math.min(300, currentZoom + 25));
	}, []);

	const handleZoomOut = useCallback(() => {
		setZoom((currentZoom) => Math.max(50, currentZoom - 25));
	}, []);

	// Disabled fit to screen for now
	const handleFitToScreen = useCallback(() => {
		// Fit to screen functionality disabled
	}, []);

	// Disabled chapter click for now
	const handleChapterClick = useCallback((_pageNumber) => {
		// Chapter click functionality disabled for testing
	}, []);

	if (loading) {
		return (
			<div className="book-viewer-loading">
				<div className="spinner">Loading book...</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="book-viewer-error">
				<h2>Error loading book</h2>
				<p>{error}</p>
			</div>
		);
	}

	if (!book) {
		return (
			<div className="book-viewer-error">
				<h2>Book not found</h2>
			</div>
		);
	}

	const fileType = book.fileType?.toLowerCase();

	return (
		<div className="flex h-screen bg-background">
			<BookHeader
				book={book}
				onToggleSidebar={() => toggleSidebarRef.current?.()}
				isSidebarOpen={sidebarOpen}
				showZoomControls={fileType === "pdf"}
				zoomLevel={zoom}
				onZoomIn={handleZoomIn}
				onZoomOut={handleZoomOut}
				onFitToScreen={handleFitToScreen}
			/>

			{sidebarOpen && (
				<BookSidebar
					book={book}
					onChapterClick={handleChapterClick}
					currentPage={1}
					progressPercentage={0}
				/>
			)}

			<main
				className={`flex-1 transition-all duration-300 ${sidebarOpen ? "ml-64" : "ml-0"} pt-16`}
			>
				<div className="book-viewer-container h-full">
					{fileType === "pdf" ? (
						<PDFErrorBoundary>
							<PDFViewer ref={pdfViewerRef} url={bookUrl} zoom={zoom} />
						</PDFErrorBoundary>
					) : fileType === "epub" ? (
						<EPUBViewer url={bookUrl} bookInfo={book} />
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

export default BookViewerContent;
