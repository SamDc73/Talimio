import { useQuery } from "@tanstack/react-query"
import { useRef } from "react"
import { useParams } from "react-router-dom"
import ErrorBoundary from "@/components/ErrorBoundary"
import { BookHeader } from "@/components/header/BookHeader"
import BookSidebarContainer from "@/features/book-viewer/components/BookSidebarContainer"
import { booksApi } from "./api/booksApi"
import EpubViewer from "./components/EpubViewer"
import PdfViewer from "./components/PdfViewer"
import {
	useBookActions,
	useBookCurrentPage,
	useBookTotalPages,
	useBookZoomLevel,
	useSidebarOpen,
	useToggleSidebar,
} from "./hooks/use-book-state"

function BookViewerStatus({ tone, title, description }) {
	if (tone === "loading") {
		return (
			<div className="flex h-screen w-full items-center justify-center bg-background">
				<div className="text-xl text-muted-foreground">{title}</div>
			</div>
		)
	}

	return (
		<div className="flex h-screen w-full flex-col items-center justify-center bg-background px-8 text-center text-foreground">
			<h2 className="mb-4 text-2xl text-destructive">{title}</h2>
			{description ? <p className="text-muted-foreground">{description}</p> : null}
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

	const { data: presigned } = useQuery({
		queryKey: ["book-presigned-url", bookId],
		queryFn: () => booksApi.getPresignedUrl(bookId),
		enabled: !!bookId,
		staleTime: 55 * 60 * 1000, // signed URLs are valid ~1h; keep stable within a session
		refetchOnWindowFocus: false,
	})
	const bookUrl = presigned?.url ?? null

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
		// Metadata extraction runs once at upload. Briefly poll so the sidebar/TOC
		// populate the moment it finishes, but stop once total_pages arrives or after
		// ~1 min so a book without extractable page count never polls forever.
		refetchInterval: (query) => (query.state.data?.totalPages || query.state.dataUpdateCount >= 20 ? false : 3000),
	})

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
	let viewerContent = (
		<BookViewerStatus
			tone="empty"
			title="Unsupported file format"
			description="Only PDF and EPUB files are supported."
		/>
	)
	if (isPdf) {
		viewerContent = <PdfViewer key={bookId} url={bookUrl} bookId={bookId} ref={viewerApiRef} />
	} else if (isEpub) {
		viewerContent = <EpubViewer key={bookId} url={bookUrl} bookId={bookId} />
	}

	return (
		<div className="flex h-screen bg-background">
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
				<BookSidebarContainer
					book={{ ...book, totalPages: sidebarTotalPages }}
					bookId={bookId}
					onChapterClick={handleChapterClick}
					currentPage={currentPage}
					progressPercentage={progressPercentage}
				/>
			) : null}

			<main className={`flex-1 transition-all duration-300 ${sidebarOpen ? "ml-64" : "ml-0"} pt-16`}>
				<div className="h-full overflow-hidden">
					<ErrorBoundary>{viewerContent}</ErrorBoundary>
				</div>
			</main>
		</div>
	)
}

export default BookViewerContent
