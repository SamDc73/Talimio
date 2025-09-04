import { useEffect, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { BookHeader } from "@/components/header/BookHeader"
import BookSidebar from "@/components/sidebar/BookSidebar"
import {
	useBookActions,
	useBookCurrentPage,
	useBookTotalPages,
	useBookZoomLevel,
	useSidebarOpen,
	useToggleSidebar,
} from "@/hooks/book-hooks"
import { booksApi } from "@/services/booksApi"
import EpubErrorBoundary from "./components/EPUBErrorBoundary"
import EpubViewer from "./components/EPUBViewer"
import PdfErrorBoundary from "./components/PDFErrorBoundary"
import PdfViewer from "./components/PDFViewer"

// CSS removed - using Tailwind classes

function BookViewerContent() {
	const { bookId } = useParams()
	const [book, setBook] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const pdfViewerRef = useRef(null)

	// Debug bookId
	useEffect(() => {}, [])

	// Get zoom and page from reading state using custom hooks
	const zoomLevel = useBookZoomLevel(bookId)
	const currentPage = useBookCurrentPage(bookId)
	const totalPages = useBookTotalPages(bookId)

	// Get store actions
	const { setBookZoom } = useBookActions()

	// Sidebar state management - use proper selectors
	const sidebarOpen = useSidebarOpen()
	const toggleSidebar = useToggleSidebar()

	// Book URL for PDF/EPUB viewers
	// Use /content endpoint which proxies through backend to avoid CORS issues
	const bookUrl = `/api/v1/books/${bookId}/content`

	useEffect(() => {
		const fetchBook = async () => {
			try {
				setLoading(true)
				const data = await booksApi.getBook(bookId)
				setBook(data)
			} catch (err) {
				setError(err.message)
			} finally {
				setLoading(false)
			}
		}
		if (bookId) {
			fetchBook()
		}
	}, [bookId]) // Only depend on bookId

	// Zoom handlers
	const handleZoomIn = () => {
		const newZoom = Math.min(300, zoomLevel + 25)
		setBookZoom(bookId, newZoom)
	}

	const handleZoomOut = () => {
		const newZoom = Math.max(50, zoomLevel - 25)
		setBookZoom(bookId, newZoom)
	}

	const handleFitToScreen = () => {
		if (pdfViewerRef.current?.fitToScreen) {
			pdfViewerRef.current.fitToScreen()
		}
	}

	const handleChapterClick = (pageNumber) => {
		if (pdfViewerRef.current?.goToPage) {
			pdfViewerRef.current.goToPage(pageNumber)
		}
	}

	if (loading) {
		return (
			<div className="w-full h-screen flex items-center justify-center bg-white">
				<div className="text-xl text-gray-500">Loading book...</div>
			</div>
		)
	}

	if (error) {
		return (
			<div className="w-full h-screen flex flex-col items-center justify-center bg-white text-gray-900 px-8 text-center">
				<h2 className="text-2xl mb-4 text-red-500">Error loading book</h2>
				<p className="text-gray-500">{error}</p>
			</div>
		)
	}

	if (!book) {
		return (
			<div className="w-full h-screen flex flex-col items-center justify-center bg-white text-gray-900 px-8 text-center">
				<h2 className="text-2xl mb-4 text-red-500">Book not found</h2>
			</div>
		)
	}

	const fileType = book.fileType?.toLowerCase()

	// Font size handlers for EPUB
	const handleFontIncrease = () => {
		const newSize = Math.min(200, zoomLevel + 25)
		setBookZoom(bookId, newSize)
	}

	const handleFontDecrease = () => {
		const newSize = Math.max(50, zoomLevel - 25)
		setBookZoom(bookId, newSize)
	}

	return (
		<div className="flex h-screen bg-white">
			<BookHeader
				book={book}
				bookId={bookId}
				onToggleSidebar={toggleSidebar}
				isSidebarOpen={sidebarOpen}
				showZoomControls={fileType === "pdf"}
				showFontControls={fileType === "epub"}
				zoomLevel={zoomLevel}
				fontSize={zoomLevel}
				onZoomIn={handleZoomIn}
				onZoomOut={handleZoomOut}
				onFitToScreen={handleFitToScreen}
				onFontIncrease={handleFontIncrease}
				onFontDecrease={handleFontDecrease}
			/>

			{sidebarOpen && (
				<BookSidebar
					book={{ ...book, totalPages: totalPages || book.totalPages }}
					bookId={bookId}
					onChapterClick={handleChapterClick}
					currentPage={currentPage}
					progressPercentage={totalPages ? Math.round((currentPage / totalPages) * 100) : 0}
				/>
			)}

			<main className={`flex-1 transition-all duration-300 ${sidebarOpen ? "ml-64" : "ml-0"} pt-16`}>
				<div className="h-full overflow-hidden">
					{fileType === "pdf" ? (
						<PdfErrorBoundary>
							<PdfViewer ref={pdfViewerRef} url={bookUrl} zoom={zoomLevel} bookId={bookId} />
						</PdfErrorBoundary>
					) : fileType === "epub" ? (
						<EpubErrorBoundary>
							<EpubViewer url={bookUrl} bookId={bookId} bookInfo={book} />
						</EpubErrorBoundary>
					) : (
						<div className="w-full h-screen flex flex-col items-center justify-center bg-white text-gray-900 px-8 text-center">
							<h2 className="text-2xl mb-4 text-red-500">Unsupported file format</h2>
							<p>Only PDF and EPUB files are supported.</p>
						</div>
					)}
				</div>
			</main>
		</div>
	)
}

export default BookViewerContent
