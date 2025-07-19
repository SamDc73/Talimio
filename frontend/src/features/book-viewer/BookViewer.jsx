import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { BookHeader } from "@/components/header/BookHeader";
import BookSidebar from "@/components/sidebar/BookSidebar";
import { BookProgressProvider, useBookProgress } from "@/hooks/useBookProgress";
import { booksApi } from "@/services/booksApi";
import useAppStore from "@/stores/useAppStore";
import EPUBViewer from "./components/EPUBViewer";
import PDFViewer from "./components/PDFViewer";
import "./BookViewer.css";

const BookViewerContent = () => {
	const { bookId } = useParams();
	const [book, setBook] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const pdfViewerRef = useRef(null);
	const { bookProgress, isChapterCompleted } = useBookProgress();
	const [currentPage, setCurrentPage] = useState(1);

	const updateBookProgress = useAppStore((state) => state.updateBookProgress);
	const setBookZoom = useAppStore((state) => state.setBookZoom);
	const storedZoom = useAppStore(
		(state) => state.books.progress[bookId]?.zoomLevel || 100,
	);
	const [zoom, setZoom] = useState(storedZoom);

	useEffect(() => {
		const fetchBook = async () => {
			try {
				setLoading(true);
				const data = await booksApi.getBook(bookId);
				setBook(data);

				// Only set initial page on first load, get current stored progress at this moment
				const currentStoredProgress =
					useAppStore.getState().books.progress[bookId];
				const currentPageToUse =
					currentStoredProgress?.currentPage &&
					currentStoredProgress.currentPage > 1
						? currentStoredProgress.currentPage
						: data.progress?.currentPage || 1;

				setCurrentPage(currentPageToUse);

				console.log(
					`📖 Book ${bookId} loaded: Using page ${currentPageToUse} (stored: ${currentStoredProgress?.currentPage}, server: ${data.progress?.currentPage})`,
				);
			} catch (err) {
				setError(err.message);
			} finally {
				setLoading(false);
			}
		};
		if (bookId) {
			fetchBook();
		}
	}, [bookId]); // Only depend on bookId, not on storedBookProgress

	// Sync local zoom state with stored zoom
	useEffect(() => {
		setZoom(storedZoom);
	}, [storedZoom]);

	const handlePageChange = useCallback(
		(page) => {
			setCurrentPage(page);
			// Persist the current page to the store
			if (bookId) {
				updateBookProgress(bookId, { currentPage: page });
				console.log(`📄 Page changed to ${page} for book ${bookId}`);
			}
		},
		[bookId, updateBookProgress],
	);

	const handleZoomChange = useCallback(
		(newZoom) => {
			setZoom(newZoom);
			if (bookId) {
				setBookZoom(bookId, newZoom);
			}
		},
		[bookId, setBookZoom],
	);

	const handleZoomIn = useCallback(() => {
		const newZoom = Math.min(300, zoom + 25);
		setZoom(newZoom);
		if (bookId) {
			setBookZoom(bookId, newZoom);
		}
	}, [zoom, bookId, setBookZoom]);

	const handleZoomOut = useCallback(() => {
		const newZoom = Math.max(50, zoom - 25);
		setZoom(newZoom);
		if (bookId) {
			setBookZoom(bookId, newZoom);
		}
	}, [zoom, bookId, setBookZoom]);

	const handleFitToScreen = useCallback(() => {
		if (pdfViewerRef.current) {
			pdfViewerRef.current.calculateFitToWidth?.();
		}
	}, []);

	const handleChapterClick = useCallback(
		(pageNumber) => {
			const fileType = book?.fileType?.toLowerCase();

			if (fileType === "pdf" && pdfViewerRef.current) {
				pdfViewerRef.current.scrollToPage?.(pageNumber);
			}

			// Update current page when navigating via chapter
			if (pageNumber && pageNumber !== currentPage) {
				handlePageChange(pageNumber);
			}

			// Chapter completion is now handled internally by the sidebar
		},
		[book?.fileType, currentPage, handlePageChange],
	);

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
	const bookUrl = `/api/v1/books/${bookId}/file`;

	return (
		<div className="flex h-screen bg-background">
			<BookHeader
				bookTitle={book.title}
				bookAuthor={book.author}
				progressPercentage={bookProgress.progressPercentage}
				currentPage={currentPage}
				totalPages={book.totalPages}
				showZoomControls={fileType === "pdf"}
				zoomLevel={zoom}
				onZoomIn={handleZoomIn}
				onZoomOut={handleZoomOut}
				onFitToScreen={handleFitToScreen}
			/>

			<BookSidebar
				book={book}
				onChapterClick={handleChapterClick}
				isChapterCompleted={isChapterCompleted}
				currentPage={currentPage}
			/>

			<main className={`flex-1 transition-all duration-300 ml-64 pt-16`}>
				<div className="book-viewer-container h-full">
					{fileType === "pdf" ? (
						<PDFViewer
							ref={pdfViewerRef}
							url={bookUrl}
							bookInfo={book}
							onPageChange={handlePageChange}
							initialPage={currentPage}
							zoom={zoom}
							onZoomChange={handleZoomChange}
						/>
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

const BookViewer = () => {
	const { bookId } = useParams();

	return (
		<BookProgressProvider bookId={bookId}>
			<BookViewerContent />
		</BookProgressProvider>
	);
};

export default BookViewer;
