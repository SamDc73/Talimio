import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { BookHeader } from "@/components/header/BookHeader";
import BookSidebar from "@/components/sidebar/BookSidebar";
import { BookProgressProvider, useBookProgress } from "@/hooks/useBookProgress";
import { booksApi } from "@/services/booksApi";
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

	useEffect(() => {
		const fetchBook = async () => {
			try {
				setLoading(true);
				const data = await booksApi.getBook(bookId);
				setBook(data);
				setCurrentPage(data.progress?.currentPage || 1);
			} catch (err) {
				setError(err.message);
			} finally {
				setLoading(false);
			}
		};
		if (bookId) {
			fetchBook();
		}
	}, [bookId]);

	const handlePageChange = useCallback((page) => {
		setCurrentPage(page);
	}, []);

	const handleChapterClick = useCallback(
		(pageNumber) => {
			const fileType = book?.fileType?.toLowerCase();

			if (fileType === "pdf" && pdfViewerRef.current) {
				pdfViewerRef.current.scrollToPage?.(pageNumber);
			}

			// Chapter completion is now handled internally by the sidebar
		},
		[book?.fileType],
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
