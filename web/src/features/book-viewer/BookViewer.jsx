import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { useParams } from "react-router-dom"
import ErrorBoundary from "@/components/ErrorBoundary"
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
import { booksApi } from "./api/booksApi"
import EpubViewer from "./components/EPUBViewer"
import PdfViewer from "./components/PDFViewer"

function BookViewerStatus({ tone, title, description }) {
	if (tone === "loading") {
		return (
			<div className="flex h-screen w-full items-center justify-center bg-white">
				<div className="text-xl text-gray-500">{title}</div>
			</div>
		)
	}

	return (
		<div className="flex h-screen w-full flex-col items-center justify-center bg-white px-8 text-center text-gray-900">
			<h2 className="mb-4 text-2xl text-red-500">{title}</h2>
			{description ? <p className="text-gray-500">{description}</p> : null}
		</div>
	)
}

function BookViewerContent() {
	const { bookId } = useParams()
	const viewerApiRef = useRef(null)

	const zoomLevel = useBookZoomLevel(bookId)
	const currentPage = useBookCurrentPage(bookId)
	const totalPages = useBookTotalPages(bookId)
	const { setBookZoom } = useBookActions()
	const sidebarOpen = useSidebarOpen()
	const toggleSidebar = useToggleSidebar()
	const bookUrl = bookId ? `/api/v1/books/${bookId}/content` : null

	const {
		data: book,
		isLoading,
		isError,
		error,
	} = useQuery({
		queryKey: ["book", bookId],
		queryFn: () => booksApi.getBook(bookId),
		enabled: Boolean(bookId),
		staleTime: 60 * 1000,
		gcTime: 5 * 60 * 1000,
		// Prevent background refetches and retry storms causing 429
		refetchOnWindowFocus: false,
		retry: false,
	})

	useEffect(() => {
		void bookId
		viewerApiRef.current = null
	}, [bookId])

	const handleZoomIn = () => {
		viewerApiRef.current?.zoomIn?.()
	}

	const handleZoomOut = () => {
		viewerApiRef.current?.zoomOut?.()
	}

	const handleFitToScreen = () => {
		viewerApiRef.current?.fitToScreen?.()
	}

	const handleChapterClick = (pageNumber) => {
		viewerApiRef.current?.goToPage?.(pageNumber)
	}

	const handleRegisterApi = (api) => {
		viewerApiRef.current = api
	}

	if (!bookId) {
		return <BookViewerStatus tone="error" title="Missing book identifier" />
	}

	if (isLoading) {
		return <BookViewerStatus tone="loading" title="Loading book..." />
	}

	if (isError) {
		const message = error instanceof Error ? error.message : "Failed to load book"
		return <BookViewerStatus tone="error" title="Error loading book" description={message} />
	}

	if (!book || !bookUrl) {
		return <BookViewerStatus tone="empty" title="Book not found" />
	}

	const fileType = book.fileType?.toLowerCase() ?? ""
	const isPdf = fileType === "pdf"
	const isEpub = fileType === "epub"
	const fallbackTotalPages = book.totalPages ?? 0
	const sidebarTotalPages = totalPages || fallbackTotalPages
	const progressPercentage = sidebarTotalPages ? Math.round(((currentPage || 0) / sidebarTotalPages) * 100) : 0

	const handleFontIncrease = () => {
		if (!isEpub) {
			return
		}
		const newSize = Math.min(200, zoomLevel + 25)
		setBookZoom(bookId, newSize)
	}

	const handleFontDecrease = () => {
		if (!isEpub) {
			return
		}
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
				showZoomControls={isPdf}
				showFontControls={isEpub}
				zoomLevel={zoomLevel}
				fontSize={zoomLevel}
				onZoomIn={handleZoomIn}
				onZoomOut={handleZoomOut}
				onFitToScreen={handleFitToScreen}
				onFontIncrease={handleFontIncrease}
				onFontDecrease={handleFontDecrease}
			/>

			{sidebarOpen ? (
				<BookSidebar
					book={{ ...book, totalPages: sidebarTotalPages }}
					bookId={bookId}
					onChapterClick={handleChapterClick}
					currentPage={currentPage}
					progressPercentage={progressPercentage}
				/>
			) : null}

			<main className={`flex-1 transition-all duration-300 ${sidebarOpen ? "ml-64" : "ml-0"} pt-16`}>
				<div className="h-full overflow-hidden">
					<ErrorBoundary>
						{isPdf ? (
							<PdfViewer url={bookUrl} bookId={bookId} registerApi={handleRegisterApi} />
						) : isEpub ? (
							<EpubViewer url={bookUrl} bookId={bookId} />
						) : (
							<BookViewerStatus
								tone="empty"
								title="Unsupported file format"
								description="Only PDF and EPUB files are supported."
							/>
						)}
					</ErrorBoundary>
				</div>
			</main>
		</div>
	)
}

export default BookViewerContent
